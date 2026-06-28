"""Write-side transaction mutations."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from finance.analytics.filters import is_expense_category_candidate
from finance.domain.category_mapping import subcategory_parent_value
from finance.domain.enums import CategorySource, TransactionType
from finance.domain.models import CategoryDef, MlFeedbackEvent, Transaction
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationPolicy,
    decide_classification,
)
from finance.ml.feedback import (
    EVENT_ACCEPT_SUGGESTION,
    EVENT_MANUAL_CATEGORY,
    EVENT_MANUAL_CLEAR,
    EVENT_REJECT_SUGGESTION,
    record_transaction_feedback,
)
from finance.profile.service import remember_merchant_category

UNCHANGED = object()


class InvalidCategoryAssignment(ValueError):
    """Raised when a category/subcategory pair would create inconsistent data."""


def _known_subcategory_parent(session: Session, subcategory: str) -> str | None:
    parent = subcategory_parent_value(subcategory)
    if parent is not None:
        return parent
    row = session.execute(
        select(CategoryDef.parent).where(CategoryDef.name == subcategory)
    ).scalar_one_or_none()
    return str(row) if row else None


def _clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = str(value).strip()
    return label or None


def _can_assign_expense_category(tx: Transaction) -> bool:
    return is_expense_category_candidate(
        tx.direction,
        tx.is_transfer,
        tx.transaction_type,
    )


def _clear_category_state(tx: Transaction) -> None:
    tx_model = cast(Any, tx)
    tx_model.category = None
    tx_model.subcategory = None
    tx_model.category_source = None
    tx_model.category_predicted = None
    tx_model.category_confidence = None
    tx_model.category_predicted_source = None
    tx_model.category_suggestion_rejected = False


def _resolve_category_assignment(
    session: Session,
    category: str | None,
    subcategory: str | None,
) -> tuple[str | None, str | None]:
    category = _clean_label(category)
    subcategory = _clean_label(subcategory)
    if subcategory is None:
        return category, None
    parent = _known_subcategory_parent(session, subcategory)
    if parent is None:
        raise InvalidCategoryAssignment("Unknown subcategory.")
    if category is None:
        return parent, subcategory
    if category != parent:
        raise InvalidCategoryAssignment(
            "Subcategory does not belong to the selected category."
        )
    return category, subcategory


def update_category(
    session: Session,
    tx_id: int,
    category: str | None,
    *,
    subcategory: str | None = None,
    remember_rule: bool = False,
) -> Transaction | None:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return None
    # A subcategory implies its parent group. Validate the pair so the ML-level
    # ``category`` field cannot drift away from the UI refinement layer.
    category, subcategory = _resolve_category_assignment(
        session, category, subcategory
    )
    if category is not None and not _can_assign_expense_category(tx):
        raise InvalidCategoryAssignment(
            "Category can only be assigned to debit expense transactions."
        )
    tx_model = cast(Any, tx)
    previous_prediction = tx.category_predicted
    previous_category = tx.category
    tx_model.category = category
    tx_model.subcategory = subcategory if category is not None else None
    tx_model.category_source = CategorySource.MANUAL.value if category is not None else None
    if category is not None:
        tx_model.category_suggestion_rejected = False
        record_transaction_feedback(
            session,
            tx,
            event_type=EVENT_MANUAL_CATEGORY,
            final_category=category,
        )
        if remember_rule:
            remember_merchant_category(session, merchant=tx.merchant, category=category)
    elif previous_prediction is not None or previous_category is not None:
        record_transaction_feedback(
            session,
            tx,
            event_type=EVENT_MANUAL_CLEAR,
            final_category=None,
        )
    session.commit()
    session.refresh(tx)
    return tx


_TRANSFER_TYPES = {
    TransactionType.OWN_TRANSFER.value,
}


def update_transaction_type(
    session: Session,
    tx_id: int,
    transaction_type: str,
) -> Transaction | None:
    """Manually override the transaction type (e.g. mark as a personal transfer).

    Keeps ``is_transfer`` consistent with the chosen type so downstream
    aggregations that exclude transfers stay correct.
    """
    try:
        value = TransactionType(transaction_type).value
    except ValueError:
        return None
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return None
    tx_model = cast(Any, tx)
    tx_model.transaction_type = value
    tx_model.is_transfer = value in _TRANSFER_TYPES
    if not _can_assign_expense_category(tx):
        _clear_category_state(tx)
    session.commit()
    session.refresh(tx)
    return tx


def _clean_tags(tags: list[str]) -> list[str]:
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


def update_annotations(
    session: Session,
    tx_id: int,
    *,
    notes: str | None | object = UNCHANGED,
    tags: list[str] | None | object = UNCHANGED,
) -> Transaction | None:
    """Set user notes and/or tags on a transaction.

    ``notes``/``tags`` are user-curated metadata and never feed the ML category
    or transaction-type semantics. Omitted fields stay unchanged; explicit
    ``None`` clears notes.
    """
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return None
    tx_model = cast(Any, tx)
    if notes is not UNCHANGED:
        trimmed = "" if notes is None else str(notes).strip()
        tx_model.notes = trimmed or None
    if tags is not UNCHANGED:
        tx_model.tags = _clean_tags(cast(list[str], tags or []))
    session.commit()
    session.refresh(tx)
    return tx


def bulk_categorize(
    session: Session,
    *,
    ids: list[int] | None,
    merchant: str | None,
    category: str | None | object = UNCHANGED,
    mark_transfer: bool | None = None,
    transaction_type: str | None = None,
) -> int:
    tx_type_value: str | None = None
    if transaction_type is not None:
        tx_type_value = TransactionType(transaction_type).value

    stmt = select(Transaction)
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    if merchant:
        stmt = stmt.where(Transaction.merchant == merchant)
    rows = session.execute(stmt).scalars().all()
    affected = 0
    for tx in rows:
        tx_model = cast(Any, tx)
        changed = False
        if mark_transfer is not None:
            tx_model.is_transfer = mark_transfer
            tx_model.transaction_type = (
                TransactionType.OWN_TRANSFER.value
                if mark_transfer
                else TransactionType.PURCHASE.value
            )
            changed = True
            if mark_transfer:
                _clear_category_state(tx)
        if tx_type_value is not None:
            tx_model.transaction_type = tx_type_value
            tx_model.is_transfer = tx_type_value in _TRANSFER_TYPES
            changed = True
            if not _can_assign_expense_category(tx):
                _clear_category_state(tx)
        if category is UNCHANGED:
            affected += int(changed)
            continue
        if category is None:
            tx_model.category = None
            tx_model.subcategory = None
            tx_model.category_source = None
            changed = True
            affected += int(changed)
            continue
        if not _can_assign_expense_category(tx):
            affected += int(changed)
            continue
        tx_model.category = category
        tx_model.subcategory = None
        tx_model.category_source = CategorySource.MANUAL.value
        tx_model.category_suggestion_rejected = False
        changed = True
        affected += int(changed)
    session.commit()
    return affected


def accept_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
    min_confidence: float,
    policy: ClassificationPolicy = DEFAULT_POLICY,
    manual: bool = False,
) -> int:
    if manual and not ids:
        return 0
    stmt = select(Transaction).where(Transaction.category.is_(None))
    stmt = stmt.where(Transaction.category_predicted.is_not(None))
    stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    stmt = stmt.where(Transaction.direction == "debit")
    stmt = stmt.where(Transaction.is_transfer.is_(False))
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    rows = session.execute(stmt).scalars().all()
    affected = 0
    for tx in rows:
        if not _can_assign_expense_category(tx):
            continue
        decision = decide_classification(
            category=tx.category_predicted,
            confidence=tx.category_confidence,
            direction=tx.direction,
            is_transfer=tx.is_transfer,
            transaction_type=tx.transaction_type,
            policy=policy,
        )
        if decision.action != "accept" and not manual:
            continue
        if (
            not manual
            and tx.category_confidence is not None
            and min_confidence > decision.threshold_used
            and tx.category_confidence < min_confidence
        ):
            continue
        tx_model = cast(Any, tx)
        record_transaction_feedback(
            session,
            tx,
            event_type=EVENT_ACCEPT_SUGGESTION,
            final_category=str(tx.category_predicted),
        )
        tx_model.category = tx.category_predicted
        tx_model.category_source = tx.category_predicted_source or CategorySource.MODEL.value
        tx_model.category_suggestion_rejected = False
        affected += 1
    session.commit()
    return affected


def reject_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
) -> int:
    stmt = select(Transaction).where(Transaction.category.is_(None))
    stmt = stmt.where(Transaction.category_predicted.is_not(None))
    stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    stmt = stmt.where(Transaction.direction == "debit")
    stmt = stmt.where(Transaction.is_transfer.is_(False))
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    rows = session.execute(stmt).scalars().all()
    affected = 0
    for tx in rows:
        if not _can_assign_expense_category(tx):
            continue
        tx_model = cast(Any, tx)
        record_transaction_feedback(
            session,
            tx,
            event_type=EVENT_REJECT_SUGGESTION,
            final_category=None,
        )
        tx_model.category_suggestion_rejected = True
        affected += 1
    session.commit()
    return affected


def restore_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
) -> int:
    stmt = select(Transaction).where(Transaction.category.is_(None))
    stmt = stmt.where(Transaction.category_predicted.is_not(None))
    stmt = stmt.where(Transaction.category_suggestion_rejected.is_(True))
    stmt = stmt.where(Transaction.direction == "debit")
    stmt = stmt.where(Transaction.is_transfer.is_(False))
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    rows = session.execute(stmt).scalars().all()
    affected = 0
    for tx in rows:
        if not _can_assign_expense_category(tx):
            continue
        tx_model = cast(Any, tx)
        tx_model.category_suggestion_rejected = False
        affected += 1
    session.commit()
    return affected


def bulk_delete(session: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    session.execute(
        update(MlFeedbackEvent)
        .where(MlFeedbackEvent.transaction_id.in_(ids))
        .values(transaction_id=None)
    )
    result = session.execute(delete(Transaction).where(Transaction.id.in_(ids)))
    session.commit()
    return int(cast(Any, result).rowcount or 0)


def delete_transaction(session: Session, tx_id: int) -> bool:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return False
    session.execute(
        update(MlFeedbackEvent)
        .where(MlFeedbackEvent.transaction_id == tx_id)
        .values(transaction_id=None)
    )
    session.delete(tx)
    session.commit()
    return True
