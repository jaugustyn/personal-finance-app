"""Single decision policy for transaction-type classification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import case

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, CategorySource, TransactionDirection, TransactionType
from finance.domain.models import Transaction
from finance.profile.service import RULE_MODE_AUTO, RuleEffect
from finance.transactions.category_provenance import personal_rule_ref
from finance.transactions.normalization import normalize_text
from finance.transactions.rules import explain_transaction_type

TYPE_ONTOLOGY_VERSION = "transaction_type_v2"
TYPE_CONFIRMATION_MANUAL = "manual"
TYPE_CONFIRMATION_ACCEPTED = "accepted_suggestion"
TYPE_GOLD_METHODS = frozenset(
    {TYPE_CONFIRMATION_MANUAL, TYPE_CONFIRMATION_ACCEPTED}
)


@dataclass(frozen=True)
class TransactionTypeDecision:
    value: str
    mode: str
    source: str
    origin_ref: str | None
    confidence: float | None = None


EXPECTED_DIRECTIONS: dict[str, frozenset[str]] = {
    TransactionType.EXPENSE.value: frozenset({TransactionDirection.DEBIT.value}),
    TransactionType.SALARY.value: frozenset({TransactionDirection.CREDIT.value}),
    TransactionType.INCOME.value: frozenset({TransactionDirection.CREDIT.value}),
    TransactionType.REFUND.value: frozenset({TransactionDirection.CREDIT.value}),
    TransactionType.OWN_TRANSFER.value: frozenset(
        {TransactionDirection.DEBIT.value, TransactionDirection.CREDIT.value}
    ),
    TransactionType.CASH_WITHDRAWAL.value: frozenset(
        {TransactionDirection.DEBIT.value}
    ),
    TransactionType.DEBT_PAYMENT.value: frozenset({TransactionDirection.DEBIT.value}),
    TransactionType.ASSET_ALLOCATION.value: frozenset(
        {TransactionDirection.DEBIT.value}
    ),
    TransactionType.OTHER.value: frozenset(
        {TransactionDirection.DEBIT.value, TransactionDirection.CREDIT.value}
    ),
}


def fallback_type(direction: object) -> str:
    return (
        TransactionType.INCOME.value
        if str(direction) == TransactionDirection.CREDIT.value
        else TransactionType.EXPENSE.value
    )


def direction_matches(transaction_type: str, direction: object) -> bool:
    return str(direction) in EXPECTED_DIRECTIONS[TransactionType(transaction_type).value]


def _bank_decision(dto: TransactionDTO) -> TransactionTypeDecision | None:
    raw = normalize_text(dto.raw_transaction_type)
    source = str(dto.source)
    if not raw:
        return None

    value: str | None = None
    if source == BankSource.PEKAO.value:
        if raw in {"transakcja karta platnicza", "platnosc blik"}:
            value = TransactionType.EXPENSE.value
        elif "wyplata gotowki" in raw or "wyplata w bankomacie" in raw:
            value = TransactionType.CASH_WITHDRAWAL.value
        elif raw in {"prowizja", "oplata bankowa", "pobranie oplaty"}:
            value = TransactionType.EXPENSE.value
    elif source == BankSource.REVOLUT.value:
        if raw == "platnosc karta":
            value = TransactionType.EXPENSE.value
        elif raw in {"wymiana", "zasilenie"}:
            value = TransactionType.OWN_TRANSFER.value
        elif raw in {"wyplata gotowki", "cash withdrawal"}:
            value = TransactionType.CASH_WITHDRAWAL.value
        elif raw in {"zwrot karta", "card payment reversed"} and str(
            dto.direction
        ) == TransactionDirection.CREDIT.value:
            value = TransactionType.REFUND.value
    if value is None:
        return None
    return TransactionTypeDecision(
        value=value,
        mode="suggest_only",
        source=CategorySource.BANK.value,
        origin_ref=f"bank_type:{source}:v1:{raw}",
    )


def decide_transaction_type(
    dto: TransactionDTO,
    *,
    personal: RuleEffect | None,
) -> TransactionTypeDecision:
    """Return the highest-precedence import/reclassification decision."""
    personal_value = personal.transaction_type if personal else None
    if not personal_value and personal and personal.is_transfer:
        personal_value = TransactionType.OWN_TRANSFER.value
    if (
        personal is not None
        and personal_value
        and personal.mode == RULE_MODE_AUTO
    ):
        value = TransactionType(personal_value).value
        return TransactionTypeDecision(
            value=value,
            mode="auto_apply",
            source=CategorySource.RULE.value,
            origin_ref=personal_rule_ref(getattr(personal.rule, "id", None)),
            confidence=None,
        )

    if personal is not None and personal_value:
        return TransactionTypeDecision(
            value=TransactionType(personal_value).value,
            mode="suggest_only",
            source=CategorySource.RULE.value,
            origin_ref=personal_rule_ref(getattr(personal.rule, "id", None)),
            confidence=None,
        )

    bank = _bank_decision(dto)
    if bank is not None:
        return bank

    rule = explain_transaction_type(
        dto.merchant,
        dto.title,
        dto.direction,
        raw_category=dto.raw_category,
    )
    return TransactionTypeDecision(
        value=TransactionType(rule.result or fallback_type(dto.direction)).value,
        mode="suggest_only",
        source=CategorySource.RULE.value,
        origin_ref=f"type_rule:v2:{rule.rule_id}",
    )


def import_type_values(decision: TransactionTypeDecision) -> dict[str, object]:
    if decision.mode == "auto_apply":
        return {
            "transaction_type": decision.value,
            "transaction_type_source": decision.source,
            "transaction_type_confirmation_method": None,
            "transaction_type_confirmed_at": None,
            "transaction_type_origin_ref": decision.origin_ref,
            "transaction_type_predicted": None,
            "transaction_type_confidence": None,
            "transaction_type_predicted_source": None,
            "transaction_type_predicted_ref": None,
            "is_transfer": decision.value == TransactionType.OWN_TRANSFER.value,
        }
    return {
        "transaction_type": None,
        "transaction_type_source": None,
        "transaction_type_confirmation_method": None,
        "transaction_type_confirmed_at": None,
        "transaction_type_origin_ref": None,
        "transaction_type_predicted": decision.value,
        "transaction_type_confidence": decision.confidence,
        "transaction_type_predicted_source": decision.source,
        "transaction_type_predicted_ref": decision.origin_ref,
        "is_transfer": False,
    }


def effective_transaction_type(tx: Transaction) -> str:
    """Return the type safe to use in financial calculations.

    A predicted type is only a review hint.  Until the user accepts it, the
    transaction keeps the deterministic direction fallback (or an explicitly
    active type such as a personal ``auto_apply`` rule).
    """
    if tx.transaction_type:
        return str(tx.transaction_type)
    return fallback_type(tx.direction)


def transaction_type_is_provisional(tx: Transaction) -> bool:
    return tx.transaction_type_confirmation_method not in TYPE_GOLD_METHODS


def transaction_type_needs_review(tx: Transaction) -> bool:
    return (
        transaction_type_is_provisional(tx)
        and tx.transaction_type_predicted is not None
        and str(tx.transaction_type_predicted) != fallback_type(tx.direction)
    )


def fallback_type_expr() -> Any:
    return case(
        (
            Transaction.direction == TransactionDirection.CREDIT.value,
            TransactionType.INCOME.value,
        ),
        else_=TransactionType.EXPENSE.value,
    )


def effective_transaction_type_expr() -> Any:
    return case(
        (Transaction.transaction_type.is_not(None), Transaction.transaction_type),
        else_=fallback_type_expr(),
    )
