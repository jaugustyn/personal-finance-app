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


def _clean_type(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned in VALID_TRANSACTION_TYPES else None


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize transaction rows into features and confirmed labels.

    Only the DB loader decides label eligibility. In-memory callers are expected
    to pass the same confirmed-label subset.
    """
    if df.empty or "transaction_type" not in df.columns:
        return pd.DataFrame(
            columns=[
                "text",
                "abs_amount",
                "direction",
                "source",
                "transaction_type",
                "label_source",
            ]
        )

    out = df.copy()
    out["transaction_type"] = out["transaction_type"].map(_clean_type)
    out = out[out["transaction_type"].notna()].copy()
    if out.empty:
        return out.assign(label_source=LABEL_SOURCE)

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
        ],
    )
    return prepare_training_frame(df)
