"""Datasets for evidence-only transaction-type classification."""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.currencies import amount_base_expr
from finance.domain.enums import TransactionType
from finance.domain.models import Transaction

VALID_TRANSACTION_TYPES = {item.value for item in TransactionType}
LABEL_SOURCE = "silver_transaction_type"


def _clean_type(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned in VALID_TRANSACTION_TYPES else None


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize transaction rows into features and silver labels.

    The label is the current ``transaction_type`` stored on the transaction.
    That value is treated as a silver label because it may come from system
    rules, personal rules or later manual edits.
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
    raw_category = out.get("raw_category", pd.Series("", index=out.index)).fillna("").astype(str)
    out["text"] = (merchant + " " + title + " " + raw_category).str.strip()
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
    return out[
        [
            "text",
            "abs_amount",
            "direction",
            "source",
            "transaction_type",
            "label_source",
        ]
    ].reset_index(drop=True)


def load_training_set(session: Session) -> pd.DataFrame:
    """Load transaction-type silver labels from the database."""
    rows = session.execute(
        select(
            amount_base_expr().label("amount"),
            Transaction.direction,
            Transaction.merchant,
            Transaction.title,
            Transaction.raw_category,
            Transaction.source,
            Transaction.transaction_type,
        )
    ).all()
    df = pd.DataFrame(
        rows,
        columns=[
            "amount",
            "direction",
            "merchant",
            "title",
            "raw_category",
            "source",
            "transaction_type",
        ],
    )
    return prepare_training_frame(df)
