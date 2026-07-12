"""Rule-based transaction metadata classification.

These rules intentionally classify *transaction type* separately from expense
category. Doubtful rows remain provisional suggestions.
"""
from __future__ import annotations

from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.transactions.system_rules import (
    RuleDecision,
    TransactionTypeRule,
    system_rules_registry,
)


def _text(merchant: str | None, title: str | None, raw_category: str | None = None) -> str:
    return f"{merchant or ''} {title or ''} {raw_category or ''}".lower()


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
        matched = _matches_rule(rule, haystack)
        if matched is not None:
            return RuleDecision(rule.result, rule.id, rule.reason, matched, rule.mode)

    if direction_value == TransactionDirection.DEBIT.value:
        return RuleDecision(
            TransactionType.EXPENSE.value,
            "tx_type.fallback.debit_expense",
            "Provisional debit fallback.",
            mode="suggest_only",
        )
    return RuleDecision(
        TransactionType.INCOME.value,
        "tx_type.fallback.credit_income",
        "Provisional credit fallback.",
        mode="suggest_only",
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
    return TransactionType(res or TransactionType.EXPENSE.value)


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
