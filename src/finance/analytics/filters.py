"""Reusable SQL filters for financial aggregations."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from finance.domain.models import Transaction
from finance.transactions.rules import (
    category_suggestion_candidate_values,
    is_category_suggestion_candidate,
)

TRUTHY_VALUES = {"1", "true", "t", "tak", "yes", "y"}


def period_filters(start: date, end: date | None = None) -> list[Any]:
    filters: list[Any] = [Transaction.booking_date >= start]
    if end is not None:
        filters.append(Transaction.booking_date <= end)
    return filters


def non_transfer_filters(*, include_transfers: bool = False) -> list[Any]:
    return [] if include_transfers else [Transaction.is_transfer.is_(False)]


def category_candidate_type_filter() -> Any:
    """SQL condition for transaction types that may receive expense categories."""
    allowed = category_suggestion_candidate_values()
    return Transaction.transaction_type.is_(None) | Transaction.transaction_type.in_(allowed)


def expense_category_candidate_filters() -> list[Any]:
    """SQL filters for rows that can carry an expense-category label."""
    return [
        Transaction.direction == "debit",
        Transaction.is_transfer.is_(False),
        category_candidate_type_filter(),
    ]


def is_expense_category_candidate(
    direction: object,
    is_transfer: object,
    transaction_type: object,
) -> bool:
    """Python equivalent of :func:`expense_category_candidate_filters`."""
    return (
        str(direction) == "debit"
        and not _truthy(is_transfer)
        and is_category_suggestion_candidate(
            None if transaction_type is None else str(transaction_type)
        )
    )


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in TRUTHY_VALUES


def transfer_mask(df: pd.DataFrame) -> pd.Series:
    """Return a robust boolean mask for transfer rows in pandas data."""
    if "is_transfer" not in df.columns:
        return pd.Series(False, index=df.index)
    series = df["is_transfer"]
    if series.dtype == bool:
        return series.fillna(False)
    return series.map(_truthy).fillna(False).astype(bool)


def expense_category_candidate_mask(
    df: pd.DataFrame,
    *,
    direction: str | None = "debit",
) -> pd.Series:
    """Pandas mask equivalent of :func:`expense_category_candidate_filters`.

    Training and synthetic evidence frames may omit ``direction`` or
    ``transaction_type``. SQL/runtime paths still require debit and use the full
    transaction schema.
    """
    mask = pd.Series(True, index=df.index)
    if direction is not None and "direction" in df.columns:
        mask &= df["direction"].astype(str) == direction
    mask &= ~transfer_mask(df)
    if "transaction_type" in df.columns:
        allowed = category_suggestion_candidate_values()
        tx_type = df["transaction_type"]
        mask &= tx_type.isna() | tx_type.astype(str).isin(allowed)
    return mask.fillna(False).astype(bool)


def debit_spending_filters(
    start: date,
    end: date | None = None,
    *,
    category: str | None = None,
    include_transfers: bool = False,
) -> list[Any]:
    filters: list[Any] = [
        Transaction.direction == "debit",
        *period_filters(start, end),
        *non_transfer_filters(include_transfers=include_transfers),
    ]
    if category:
        filters.append(Transaction.category == category)
    return filters
