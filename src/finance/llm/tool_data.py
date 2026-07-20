"""Shared data loaders for assistant tools."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import transfer_mask
from finance.currencies import amount_base_expr
from finance.domain.models import Transaction


def load_transactions_df(session: Session) -> pd.DataFrame:
    rows = session.execute(
        select(
            Transaction.id,
            Transaction.booking_date,
            Transaction.amount.label("original_amount"),
            amount_base_expr().label("amount"),
            Transaction.currency,
            Transaction.direction,
            Transaction.merchant,
            Transaction.title,
            Transaction.category,
            Transaction.category_predicted,
            Transaction.is_transfer,
            Transaction.transaction_type,
        ).where(amount_base_expr().is_not(None))
    ).all()
    df = pd.DataFrame(
        rows,
        columns=[
            "id",
            "booking_date",
            "original_amount",
            "amount",
            "currency",
            "direction",
            "merchant",
            "title",
            "category",
            "category_predicted",
            "is_transfer",
            "transaction_type",
        ],
    )
    if df.empty:
        return df
    df["original_amount"] = df["original_amount"].astype(float)
    df["amount"] = df["amount"].astype(float)
    df["abs_amount"] = df["amount"].abs()
    df["is_transfer"] = transfer_mask(df)
    return df
