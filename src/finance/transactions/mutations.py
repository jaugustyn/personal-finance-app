"""Write-side transaction mutations."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from finance.db import command_transaction
from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationPolicy,
)
from finance.transactions.category_assignment import CategoryAssignmentService
from finance.transactions.mutation_rules import InvalidCategoryAssignment, clean_tags
from finance.transactions.suggestions import SuggestionAcceptanceService
from finance.transactions.type_service import (
    TransactionTypeDirectionMismatch,
    TransactionTypeService,
)

UNCHANGED = object()

__all__ = [
    "UNCHANGED",
    "InvalidCategoryAssignment",
    "TransactionTypeDirectionMismatch",
    "accept_suggestions",
    "bulk_categorize",
    "bulk_delete",
    "delete_transaction",
    "reject_suggestions",
    "restore_suggestions",
    "update_annotations",
    "update_category",
    "update_transaction_type",
]


def update_category(
    session: Session,
    tx_id: int,
    category: str | None,
    *,
    subcategory: str | None = None,
    remember_rule: bool = False,
) -> Transaction | None:
    return CategoryAssignmentService(session).update_category(
        tx_id,
        category,
        subcategory=subcategory,
        remember_rule=remember_rule,
    )


def update_transaction_type(
    session: Session,
    tx_id: int,
    transaction_type: str,
    *,
    allow_direction_mismatch: bool = False,
) -> Transaction | None:
    return TransactionTypeService(session).update_transaction_type(
        tx_id,
        transaction_type,
        allow_direction_mismatch=allow_direction_mismatch,
    )


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
    with command_transaction(session):
        if notes is not UNCHANGED:
            trimmed = "" if notes is None else str(notes).strip()
            tx_model.notes = trimmed or None
        if tags is not UNCHANGED:
            tx_model.tags = clean_tags(cast(list[str], tags or []))
    session.refresh(tx)
    return tx


def bulk_categorize(
    session: Session,
    *,
    ids: list[int] | None,
    merchant: str | None,
    merchant_canonical_key: str | None = None,
    category: str | None | object = UNCHANGED,
    mark_transfer: bool | None = None,
    transaction_type: str | None = None,
    allow_direction_mismatch: bool = False,
) -> int:
    return CategoryAssignmentService(session).bulk_categorize(
        ids=ids,
        merchant=merchant,
        merchant_canonical_key=merchant_canonical_key,
        category=category,
        mark_transfer=mark_transfer,
        transaction_type=transaction_type,
        allow_direction_mismatch=allow_direction_mismatch,
        unchanged=UNCHANGED,
    )


def accept_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
    min_confidence: float,
    policy: ClassificationPolicy = DEFAULT_POLICY,
    manual: bool = False,
) -> int:
    return SuggestionAcceptanceService(session).accept_suggestions(
        ids=ids,
        min_confidence=min_confidence,
        policy=policy,
        manual=manual,
    )


def reject_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
) -> int:
    return SuggestionAcceptanceService(session).reject_suggestions(ids=ids)


def restore_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
) -> int:
    return SuggestionAcceptanceService(session).restore_suggestions(ids=ids)


def bulk_delete(session: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    with command_transaction(session):
        session.execute(
            update(MlFeedbackEvent)
            .where(MlFeedbackEvent.transaction_id.in_(ids))
            .values(transaction_id=None)
        )
        result = session.execute(delete(Transaction).where(Transaction.id.in_(ids)))
    return int(cast(Any, result).rowcount or 0)


def delete_transaction(session: Session, tx_id: int) -> bool:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return False
    with command_transaction(session):
        session.execute(
            update(MlFeedbackEvent)
            .where(MlFeedbackEvent.transaction_id == tx_id)
            .values(transaction_id=None)
        )
        session.delete(tx)
    return True
