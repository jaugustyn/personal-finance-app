"""Pure transaction import policy.

This module decides how parsed transaction DTOs become persisted transaction
values. It intentionally does not read from or write to the database.
"""
from __future__ import annotations

from dataclasses import dataclass

from finance.analytics.filters import is_expense_category_candidate
from finance.currencies import ConversionResult
from finance.domain.dto import TransactionDTO
from finance.domain.enums import CategorySource, TransactionType
from finance.profile.service import RULE_MODE_AUTO, RuleEffect
from finance.transactions.rules import (
    detect_transaction_type,
    rule_category_for_type,
)


@dataclass(frozen=True)
class TransactionImportPolicy:
    skip_categories: bool = False

    def build_transaction_values(
        self,
        dto: TransactionDTO,
        *,
        converted: ConversionResult,
        personal: RuleEffect | None,
        import_id: int | None,
        dedup_hash: str,
    ) -> dict[str, object]:
        return build_transaction_values(
            dto,
            converted=converted,
            personal=personal,
            import_id=import_id,
            dedup_hash=dedup_hash,
            skip_categories=self.skip_categories,
        )


def build_transaction_values(
    dto: TransactionDTO,
    *,
    converted: ConversionResult,
    personal: RuleEffect | None,
    import_id: int | None,
    dedup_hash: str,
    skip_categories: bool = False,
) -> dict[str, object]:
    """Build DB values for a parsed transaction using deterministic policy inputs."""
    system_transaction_type = detect_transaction_type(
        dto.merchant,
        dto.title,
        dto.direction,
        raw_category=dto.raw_category,
    )
    transaction_type = (
        personal.transaction_type
        if personal and personal.transaction_type
        else system_transaction_type.value
    )
    is_transfer = (
        personal.is_transfer
        if personal and personal.is_transfer is not None
        else transaction_type == "own_transfer"
    )

    can_assign_category = is_expense_category_candidate(
        dto.direction.value,
        is_transfer,
        transaction_type,
    )
    rule_category = rule_category_for_type(TransactionType(transaction_type))
    category = (
        dto.category.value
        if dto.category and can_assign_category and not skip_categories
        else None
    )
    category_source = CategorySource.BANK.value if category is not None else None
    if category is None and rule_category is not None and can_assign_category:
        category = rule_category.value
        category_source = CategorySource.RULE.value

    category_predicted = None
    category_confidence = None
    category_predicted_source = None
    if personal and personal.category and category is None and can_assign_category:
        if personal.mode == RULE_MODE_AUTO:
            category = personal.category
            category_source = CategorySource.RULE.value
        else:
            category_predicted = personal.category
            category_confidence = personal.confidence
            category_predicted_source = CategorySource.RULE.value

    return {
        "booking_date": dto.booking_date,
        "booking_datetime": dto.booking_datetime,
        "amount": dto.amount,
        "currency": dto.currency,
        "amount_base": converted.amount_base,
        "base_currency": converted.base_currency,
        "fx_rate": converted.fx_rate,
        "fx_rate_date": converted.fx_rate_date,
        "fx_rate_source": converted.fx_rate_source,
        "direction": dto.direction.value,
        "merchant": dto.merchant,
        "title": dto.title,
        "raw_category": dto.raw_category,
        "category": category,
        "category_source": category_source,
        "category_predicted": category_predicted,
        "category_confidence": category_confidence,
        "category_predicted_source": category_predicted_source,
        "source": dto.source.value,
        "external_id": dto.external_id,
        "dedup_hash": dedup_hash,
        "import_id": import_id,
        "transaction_type": transaction_type,
        "is_transfer": bool(is_transfer),
    }
