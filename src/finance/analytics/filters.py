"""Reusable SQL filters for financial aggregations."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from finance.domain.enums import TransactionDirection, TransactionType
from finance.domain.models import Transaction
from finance.transactions.type_decision import effective_transaction_type_expr

TRUTHY_VALUES = {"1", "true", "t", "tak", "yes", "y"}


def period_filters(start: date, end: date | None = None) -> list[Any]:
    filters: list[Any] = [Transaction.booking_date >= start]
    if end is not None:
        filters.append(Transaction.booking_date <= end)
    return filters


def non_transfer_filters(*, include_transfers: bool = False) -> list[Any]:
    if include_transfers:
        return []
    return [
        Transaction.is_transfer.is_(False),
        effective_transaction_type_expr() != TransactionType.OWN_TRANSFER.value,
    ]


def category_candidate_type_filter() -> Any:
    """SQL condition for transaction types that may receive expense categories."""
    return effective_transaction_type_expr().in_(
        [TransactionType.EXPENSE.value, TransactionType.REFUND.value]
    )


def expense_category_candidate_filters() -> list[Any]:
    """SQL filters for rows that can carry an expense-category label."""
    effective_type = effective_transaction_type_expr()
    return [
        Transaction.is_transfer.is_(False),
        (
            (
                (Transaction.direction == TransactionDirection.DEBIT.value)
                & (effective_type == TransactionType.EXPENSE.value)
            )
            | (
                (Transaction.direction == TransactionDirection.CREDIT.value)
                & (effective_type == TransactionType.REFUND.value)
            )
        ),
    ]


def is_expense_category_candidate(
    direction: object,
    is_transfer: object,
    transaction_type: object,
) -> bool:
    """Python equivalent of :func:`expense_category_candidate_filters`."""
    value = None if transaction_type is None else str(transaction_type)
    return not _truthy(is_transfer) and (
        (
            str(direction) == TransactionDirection.DEBIT.value
            and value == TransactionType.EXPENSE.value
        )
        or (
            str(direction) == TransactionDirection.CREDIT.value
            and value == TransactionType.REFUND.value
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
    direction: str | None = TransactionDirection.DEBIT.value,
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
        if direction == TransactionDirection.DEBIT.value:
            allowed = {TransactionType.EXPENSE.value}
        elif direction == TransactionDirection.CREDIT.value:
            allowed = {TransactionType.REFUND.value}
        else:
            allowed = {TransactionType.EXPENSE.value, TransactionType.REFUND.value}
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
        Transaction.direction == TransactionDirection.DEBIT.value,
        effective_transaction_type_expr() == TransactionType.EXPENSE.value,
        *period_filters(start, end),
        *non_transfer_filters(include_transfers=include_transfers),
    ]
    if category:
        filters.append(Transaction.category == category)
    return filters
