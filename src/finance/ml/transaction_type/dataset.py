"""Datasets for evidence-only transaction-type classification."""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.currencies import amount_base_expr
from finance.domain.enums import TRANSACTION_TYPE_VALUES
from finance.domain.models import Transaction
from finance.transactions.type_decision import TYPE_GOLD_METHODS

VALID_TRANSACTION_TYPES = TRANSACTION_TYPE_VALUES
LABEL_SOURCE = "confirmed_transaction_type"
TYPE_PROVENANCE_COLUMNS = {
    "transaction_type",
    "transaction_type_confirmation_method",
    "transaction_type_confirmed_at",
}


def _clean_type(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned in VALID_TRANSACTION_TYPES else None


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize transaction rows into features and confirmed labels.

    In-memory and DB callers must provide explicit gold-label provenance.
    """
    if df.empty or not TYPE_PROVENANCE_COLUMNS.issubset(df.columns):
        return pd.DataFrame(
            columns=[
                "text",
                "abs_amount",
                "direction",
                "source",
                "transaction_type",
                "transaction_type_confirmation_method",
                "transaction_type_confirmed_at",
                "label_source",
            ]
        )

    out = df[
        df["transaction_type_confirmation_method"].isin(TYPE_GOLD_METHODS)
        & df["transaction_type_confirmed_at"].notna()
    ].copy()
    out["transaction_type"] = out["transaction_type"].map(_clean_type)
    out = out[out["transaction_type"].notna()].copy()
    if out.empty:
        return out.assign(label_source=LABEL_SOURCE)

    if "text" not in out.columns:
        merchant = out.get("merchant", pd.Series("", index=out.index)).fillna("").astype(str)
        title = out.get("title", pd.Series("", index=out.index)).fillna("").astype(str)
        raw_type = out.get("raw_transaction_type", pd.Series("", index=out.index))
        raw_type = raw_type.fillna("").astype(str)
        out["text"] = (merchant + " " + title + " " + raw_type).str.strip()
    out["text"] = out["text"].where(out["text"].str.len() > 0, "(missing)")

    if "abs_amount" in out.columns:
        out["abs_amount"] = out["abs_amount"].astype(float).abs()
    elif "amount" in out.columns:
        out["abs_amount"] = out["amount"].map(lambda value: float(abs(value or Decimal(0))))
    else:
        out["abs_amount"] = 0.0

    out["direction"] = out.get("direction", "unknown")
    out["direction"] = out["direction"].fillna("unknown").astype(str)
    out["source"] = out.get("source", "unknown")
    out["source"] = out["source"].fillna("unknown").astype(str)
    out["label_source"] = LABEL_SOURCE
    columns = [
        "text",
        "abs_amount",
        "direction",
        "source",
        "transaction_type",
        "transaction_type_confirmation_method",
        "transaction_type_confirmed_at",
        "label_source",
    ]
    columns.extend(
        column
        for column in ("transaction_id", "booking_date", "merchant")
        if column in out.columns
    )
    return out[columns].reset_index(drop=True)


def load_training_set(session: Session) -> pd.DataFrame:
    """Load only explicitly confirmed transaction-type gold labels."""
    rows = session.execute(
        select(
            amount_base_expr().label("amount"),
            Transaction.id,
            Transaction.booking_date,
            Transaction.direction,
            Transaction.merchant,
            Transaction.title,
            Transaction.raw_transaction_type,
            Transaction.source,
            Transaction.transaction_type,
            Transaction.transaction_type_confirmation_method,
            Transaction.transaction_type_confirmed_at,
        )
        .where(Transaction.transaction_type_confirmation_method.in_(TYPE_GOLD_METHODS))
        .where(Transaction.transaction_type_confirmed_at.is_not(None))
    ).all()
    df = pd.DataFrame(
        rows,
        columns=[
            "amount",
            "transaction_id",
            "booking_date",
            "direction",
            "merchant",
            "title",
            "raw_transaction_type",
            "source",
            "transaction_type",
            "transaction_type_confirmation_method",
            "transaction_type_confirmed_at",
        ],
    )
    return prepare_training_frame(df)
