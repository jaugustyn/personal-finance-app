"""Write-side transaction mutations."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finance.domain.enums import CategorySource, TransactionType
from finance.domain.models import Transaction
from finance.profile.service import remember_merchant_category
from finance.transactions.rules import is_category_suggestion_candidate


def update_category(
    session: Session,
    tx_id: int,
    category: str | None,
    *,
    remember_rule: bool = False,
) -> Transaction | None:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return None
    tx_model = cast(Any, tx)
    tx_model.category = category
    tx_model.category_source = CategorySource.MANUAL.value if category is not None else None
    if category is not None:
        tx_model.category_suggestion_rejected = False
        if remember_rule:
            remember_merchant_category(session, merchant=tx.merchant, category=category)
    session.commit()
    session.refresh(tx)
    return tx


def bulk_categorize(
    session: Session,
    *,
    ids: list[int] | None,
    merchant: str | None,
    category: str | None,
    mark_transfer: bool | None,
) -> int:
    stmt = select(Transaction)
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    if merchant:
        stmt = stmt.where(Transaction.merchant == merchant)
    rows = session.execute(stmt).scalars().all()
    for tx in rows:
        tx_model = cast(Any, tx)
        tx_model.category = category
        tx_model.category_source = CategorySource.MANUAL.value if category is not None else None
        if category is not None:
            tx_model.category_suggestion_rejected = False
        if mark_transfer is not None:
            tx_model.is_transfer = mark_transfer
            tx_model.transaction_type = (
                TransactionType.OWN_TRANSFER.value
                if mark_transfer
                else TransactionType.PURCHASE.value
            )
    session.commit()
    return len(rows)


def accept_suggestions(
    session: Session,
    *,
    ids: list[int] | None,
    min_confidence: float,
) -> int:
    stmt = select(Transaction).where(Transaction.category.is_(None))
    stmt = stmt.where(Transaction.category_predicted.is_not(None))
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    rows = session.execute(stmt).scalars().all()
    affected = 0
    for tx in rows:
        if not is_category_suggestion_candidate(tx.transaction_type):
            continue
        confidence = tx.category_confidence
        if confidence is not None and confidence < min_confidence:
            continue
        tx_model = cast(Any, tx)
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
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    rows = session.execute(stmt).scalars().all()
    for tx in rows:
        tx_model = cast(Any, tx)
        tx_model.category_predicted = None
        tx_model.category_confidence = None
        tx_model.category_predicted_source = None
        tx_model.category_suggestion_rejected = True
    session.commit()
    return len(rows)


def bulk_delete(session: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    result = session.execute(delete(Transaction).where(Transaction.id.in_(ids)))
    session.commit()
    return int(cast(Any, result).rowcount or 0)


def delete_transaction(session: Session, tx_id: int) -> bool:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return False
    session.delete(tx)
    session.commit()
    return True
