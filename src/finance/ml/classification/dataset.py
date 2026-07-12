"""Build training DataFrames from parsed DTOs or from the database."""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.currencies import amount_base_expr
from finance.domain.dto import TransactionDTO
from finance.domain.enums import (
    CATEGORY_CONFIRMATION_METHOD_VALUES,
    CATEGORY_VALUES,
)
from finance.domain.models import Transaction
from finance.transactions.type_decision import effective_transaction_type_expr


def dtos_to_dataframe(dtos: Iterable[TransactionDTO]) -> pd.DataFrame:
    """Convert DTOs into the feature DataFrame the pipeline expects.

    Returned columns: text, abs_amount, day_of_week, category (label, may be None),
    plus passthrough metadata (merchant, title, source, booking_date) for EDA.
    """
    rows = []
    for d in dtos:
        rows.append(
            {
                "text": f"{d.merchant} {d.title}".strip(),
                "abs_amount": float(abs(d.amount or Decimal(0))),
                "day_of_week": d.booking_date.weekday(),
                "category": d.category.value if d.category else None,
                "merchant": d.merchant,
                "title": d.title,
                "source": d.source.value,
                "booking_date": d.booking_date,
                "raw_category": d.raw_category,
                "direction": d.direction.value,
                "is_transfer": False,
                "transaction_type": "expense",
            }
        )
    return pd.DataFrame(rows)


def load_training_set(session: Session) -> pd.DataFrame:
    """Load only explicitly confirmed system-category gold labels from the DB."""
    stmt = select(Transaction, amount_base_expr().label("base_amount")).where(
        Transaction.category.in_(CATEGORY_VALUES)
    )
    stmt = stmt.where(
        Transaction.category_confirmation_method.in_(CATEGORY_CONFIRMATION_METHOD_VALUES),
        Transaction.category_confirmed_at.is_not(None),
    )
    stmt = stmt.where(*expense_category_candidate_filters())
    stmt = stmt.where(
        Transaction.direction == "debit",
        effective_transaction_type_expr() == "expense",
    )
    rows = session.execute(stmt).all()
    data = []
    for r, base_amount in rows:
        data.append(
            {
                "transaction_id": r.id,
                "text": f"{r.merchant} {r.title}".strip(),
                "abs_amount": float(abs(base_amount or Decimal(0))),
                "day_of_week": r.booking_date.weekday(),
                "category": r.category,
                "category_confirmation_method": r.category_confirmation_method,
                "category_confirmed_at": r.category_confirmed_at,
                "category_origin_ref": r.category_origin_ref,
                "merchant": r.merchant,
                "title": r.title,
                "source": r.source,
                "booking_date": r.booking_date,
                "raw_category": r.raw_category,
                "direction": r.direction,
                "is_transfer": r.is_transfer,
                "transaction_type": "expense",
            }
        )
    return pd.DataFrame(data)
