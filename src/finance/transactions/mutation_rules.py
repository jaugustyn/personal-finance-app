"""Shared rules for write-side transaction use cases."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import is_expense_category_candidate
from finance.domain.category_mapping import subcategory_parent_value
from finance.domain.enums import TransactionType
from finance.domain.models import CategoryDef, Transaction
from finance.transactions.type_decision import effective_transaction_type


class InvalidCategoryAssignment(ValueError):
    """Raised when a category/subcategory pair would create inconsistent data."""


TRANSFER_TYPES = {
    TransactionType.OWN_TRANSFER.value,
}


def known_subcategory_parent(session: Session, subcategory: str) -> str | None:
    parent = subcategory_parent_value(subcategory)
    if parent is not None:
        return parent
    row = session.execute(
        select(CategoryDef.parent).where(CategoryDef.name == subcategory)
    ).scalar_one_or_none()
    return str(row) if row else None


def clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = str(value).strip()
    return label or None


def can_assign_expense_category(tx: Transaction) -> bool:
    return is_expense_category_candidate(
        tx.direction,
        tx.is_transfer,
        effective_transaction_type(tx),
    )


def clear_category_state(tx: Transaction) -> None:
    tx_model = cast(Any, tx)
    tx_model.category = None
    tx_model.subcategory = None
    tx_model.category_source = None
    tx_model.category_confirmation_method = None
    tx_model.category_confirmed_at = None
    tx_model.category_origin_ref = None
    tx_model.category_predicted = None
    tx_model.category_confidence = None
    tx_model.category_predicted_source = None
    tx_model.category_predicted_ref = None
    tx_model.category_suggestion_rejected = False


def resolve_category_assignment(
    session: Session,
    category: str | None,
    subcategory: str | None,
) -> tuple[str | None, str | None]:
    category = clean_label(category)
    subcategory = clean_label(subcategory)
    if subcategory is None:
        return category, None
    parent = known_subcategory_parent(session, subcategory)
    if parent is None:
        raise InvalidCategoryAssignment("Unknown subcategory.")
    if category is None:
        return parent, subcategory
    if category != parent:
        raise InvalidCategoryAssignment(
            "Subcategory does not belong to the selected category."
        )
    return category, subcategory


def clean_tags(tags: list[str]) -> list[str]:
    """Trim, drop blanks and de-duplicate tags while preserving order."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned
