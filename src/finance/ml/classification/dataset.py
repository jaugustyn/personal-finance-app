"""Build training DataFrames from parsed DTOs or from the database."""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.dto import TransactionDTO
from finance.domain.models import Transaction
from finance.transactions.rules import is_category_suggestion_candidate


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
                "transaction_type": "purchase",
            }
        )
    return pd.DataFrame(rows)


def load_training_set(session: Session) -> pd.DataFrame:
    """Load all transactions with a non-null `category` from the DB."""
    stmt = select(Transaction).where(Transaction.category.is_not(None))
    stmt = stmt.where(Transaction.is_transfer.is_(False))
    rows = session.execute(stmt).scalars().all()
    data = []
    for r in rows:
        if not is_category_suggestion_candidate(r.transaction_type):
            continue
        data.append(
            {
                "text": f"{r.merchant} {r.title}".strip(),
                "abs_amount": float(abs(r.amount or Decimal(0))),
                "day_of_week": r.booking_date.weekday(),
                "category": r.category,
                "merchant": r.merchant,
                "title": r.title,
                "source": r.source,
                "booking_date": r.booking_date,
                "raw_category": r.raw_category,
                "direction": r.direction,
                "is_transfer": r.is_transfer,
                "transaction_type": r.transaction_type,
            }
        )
    return pd.DataFrame(data)
