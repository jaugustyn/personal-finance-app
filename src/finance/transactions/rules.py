"""Rule-based transaction metadata classification.

These rules intentionally classify *transaction type* separately from expense
category. They are conservative: a doubtful card/payment row stays ``purchase``
so the ML category suggester can handle it.
"""
from __future__ import annotations

from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.transactions.normalization import normalize_text
from finance.transactions.system_rules import (
    RuleDecision,
    SystemRulesRegistry,
    TransactionTypeRule,
    system_rules_registry,
)


def _text(merchant: str | None, title: str | None, raw_category: str | None = None) -> str:
    return f"{merchant or ''} {title or ''} {raw_category or ''}".lower()


def _looks_like_person_counterparty(
    merchant: str | None,
    registry: SystemRulesRegistry,
) -> bool:
    norm = normalize_text(merchant)
    if not norm:
        return False
    tokens = [token for token in norm.split() if token]
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    if any(token in registry.business_counterparty_terms for token in tokens):
        return False
    return all(token.isalpha() and len(token) >= 2 for token in tokens)


def _person_transfer_decision(
    merchant: str | None,
    haystack: str,
    raw_category: str | None,
    registry: SystemRulesRegistry,
) -> RuleDecision | None:
    raw_norm = normalize_text(raw_category)
    for term in registry.person_transfer_exclusions:
        if term in haystack:
            return None
    if raw_norm in registry.person_transfer_source_categories:
        return RuleDecision(
            TransactionType.PERSON_TRANSFER.value,
            "tx_type.person_transfer.semantic",
            "Raw/source category marks a private transfer.",
            raw_norm,
        )
    for pattern in registry.person_transfer_patterns:
        match = pattern.search(haystack)
        if match:
            return RuleDecision(
                TransactionType.PERSON_TRANSFER.value,
                "tx_type.person_transfer.semantic",
                "Transfer marker in merchant/title.",
                match.group(0),
            )
    if _looks_like_person_counterparty(merchant, registry) and any(
        keyword in haystack for keyword in registry.person_refund_keywords
    ):
        return RuleDecision(
            TransactionType.PERSON_TRANSFER.value,
            "tx_type.person_transfer.semantic",
            "Person-like counterparty with private settlement marker.",
            merchant,
        )
    return None


def _matches_rule(rule: TransactionTypeRule, haystack: str) -> str | None:
    for keyword in rule.keywords:
        if keyword in haystack:
            return keyword
    for pattern in rule.regexes:
        match = pattern.search(haystack)
        if match:
            return match.group(0)
    return None


def explain_transaction_type(
    merchant: str | None,
    title: str | None,
    direction: str | TransactionDirection,
    *,
    raw_category: str | None = None,
) -> RuleDecision:
    """Return the transaction-type decision with the matched system rule."""
    registry = system_rules_registry()
    haystack = _text(merchant, title, raw_category)
    direction_value = str(direction)

    for rule in registry.transaction_type_rules:
        if rule.direction is not None and direction_value != rule.direction:
            continue
        if rule.special == "person_transfer":
            decision = _person_transfer_decision(merchant, haystack, raw_category, registry)
            if decision is not None:
                return RuleDecision(rule.result, rule.id, rule.reason, decision.matched)
            continue
        matched = _matches_rule(rule, haystack)
        if matched is not None:
            return RuleDecision(rule.result, rule.id, rule.reason, matched)

    if direction_value == TransactionDirection.DEBIT:
        return RuleDecision(
            TransactionType.PURCHASE.value,
            "tx_type.fallback.debit_purchase",
            "Debit fallback for expense-like transactions.",
        )
    return RuleDecision(
        TransactionType.INCOME.value,
        "tx_type.fallback.credit_income",
        "Credit fallback for uncategorised inflows.",
    )


def detect_transaction_type(
    merchant: str | None,
    title: str | None,
    direction: str | TransactionDirection,
    *,
    raw_category: str | None = None,
) -> TransactionType:
    res = explain_transaction_type(
        merchant,
        title,
        direction,
        raw_category=raw_category,
    ).result
    return TransactionType(res or TransactionType.PURCHASE.value)


def detect_transfer(merchant: str | None, title: str | None) -> bool:
    return detect_transaction_type(
        merchant,
        title,
        TransactionDirection.DEBIT,
    ) == TransactionType.OWN_TRANSFER


def rule_category_for_type(transaction_type: TransactionType) -> Category | None:
    category = system_rules_registry().category_for_transaction_type(transaction_type)
    return Category(category) if category is not None else None


def is_category_suggestion_candidate(transaction_type: str | TransactionType | None) -> bool:
    if transaction_type is None:
        return True
    value = str(transaction_type)
    return value in system_rules_registry().category_suggestion_candidate_types


def category_suggestion_candidate_values() -> frozenset[str]:
    """Transaction types that can carry an expense-category label."""
    return system_rules_registry().category_suggestion_candidate_types
