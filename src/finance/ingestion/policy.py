"""Pure transaction import policy.

This module decides how parsed transaction DTOs become persisted transaction
values. It intentionally does not read from or write to the database.
"""
from __future__ import annotations

from dataclasses import dataclass

from finance.analytics.filters import is_expense_category_candidate
from finance.currencies import ConversionResult
from finance.domain.dto import TransactionDTO
from finance.domain.enums import (
    CategoryConfirmationMethod,
    CategorySource,
    TransactionType,
)
from finance.profile.service import RULE_MODE_AUTO, RuleEffect
from finance.transactions.category_provenance import (
    bank_mapping_ref,
    personal_rule_ref,
    system_rule_ref,
)
from finance.transactions.rules import rule_category_for_type
from finance.transactions.type_decision import (
    decide_transaction_type,
    import_type_values,
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
    type_decision = decide_transaction_type(dto, personal=personal)
    type_values = import_type_values(type_decision)
    # Suggestions are not financial facts.  They must not change category
    # eligibility before explicit acceptance.
    transaction_type = (
        type_decision.value
        if type_decision.mode == "auto_apply"
        else (
            TransactionType.INCOME.value
            if dto.direction.value == "credit"
            else TransactionType.EXPENSE.value
        )
    )
    is_transfer = transaction_type == TransactionType.OWN_TRANSFER.value

    can_assign_category = is_expense_category_candidate(
        dto.direction.value,
        is_transfer,
        transaction_type,
    )
    rule_category = rule_category_for_type(TransactionType(transaction_type))
    category = None
    category_source = None
    category_confirmation_method = None
    category_confirmed_at = None
    category_origin_ref = None
    category_predicted = None
    category_confidence = None
    category_predicted_source = None
    category_predicted_ref = None

    if personal and personal.category and can_assign_category:
        if personal.mode == RULE_MODE_AUTO:
            category = personal.category
            category_source = CategorySource.RULE.value
            category_confirmation_method = CategoryConfirmationMethod.PERSONAL_RULE_AUTO.value
            category_confirmed_at = None
            category_origin_ref = personal_rule_ref(getattr(personal.rule, "id", None))
        else:
            category_predicted = personal.category
            category_confidence = personal.confidence
            category_predicted_source = CategorySource.RULE.value
            category_predicted_ref = personal_rule_ref(getattr(personal.rule, "id", None))
    elif dto.category and can_assign_category and not skip_categories:
        category_predicted = dto.category.value
        category_predicted_source = CategorySource.BANK.value
        category_predicted_ref = bank_mapping_ref(dto.source.value)
    elif rule_category is not None and can_assign_category:
        category_predicted = rule_category.value
        category_predicted_source = CategorySource.RULE.value
        category_predicted_ref = system_rule_ref(transaction_type)

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
        "raw_transaction_type": dto.raw_transaction_type,
        "category": category,
        "category_source": category_source,
        "category_confirmation_method": category_confirmation_method,
        "category_confirmed_at": category_confirmed_at,
        "category_origin_ref": category_origin_ref,
        "category_predicted": category_predicted,
        "category_confidence": category_confidence,
        "category_predicted_source": category_predicted_source,
        "category_predicted_ref": category_predicted_ref,
        "source": dto.source.value,
        "external_id": dto.external_id,
        "dedup_hash": dedup_hash,
        "import_id": import_id,
        **type_values,
    }
