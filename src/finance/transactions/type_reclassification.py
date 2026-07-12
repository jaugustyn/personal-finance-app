"""Recalculate non-gold transaction-type decisions."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.domain.models import Transaction
from finance.profile.service import effect_for_transaction
from finance.transactions.type_decision import (
    TYPE_GOLD_METHODS,
    decide_transaction_type,
)
from finance.transactions.type_service import TransactionTypeService


def reclassify_transaction_types(
    session: Session,
    *,
    ids: list[int] | None = None,
    import_id: int | None = None,
) -> int:
    stmt = select(Transaction).where(
        Transaction.transaction_type_confirmation_method.not_in(TYPE_GOLD_METHODS)
        | Transaction.transaction_type_confirmation_method.is_(None)
    )
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    if import_id is not None:
        stmt = stmt.where(Transaction.import_id == import_id)
    rows = list(session.execute(stmt).scalars())
    service = TransactionTypeService(session)
    updated = 0
    for tx in rows:
        dto = TransactionDTO(
            booking_date=tx.booking_date,
            booking_datetime=tx.booking_datetime,
            amount=Decimal(tx.amount),
            currency=str(tx.currency),
            direction=TransactionDirection(str(tx.direction)),
            merchant=tx.merchant,
            title=tx.title,
            raw_category=tx.raw_category,
            raw_transaction_type=tx.raw_transaction_type,
            source=BankSource(str(tx.source)),
            external_id=tx.external_id,
        )
        personal = effect_for_transaction(
            session,
            merchant=tx.merchant,
            title=tx.title,
        )
        decision = decide_transaction_type(dto, personal=personal)
        updated += int(service.apply_decision(tx, decision))
    session.commit()
    return updated
