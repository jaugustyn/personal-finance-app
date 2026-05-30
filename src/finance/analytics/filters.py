"""Reusable SQL filters for financial aggregations."""
from __future__ import annotations

from datetime import date
from typing import Any

from finance.domain.models import Transaction


def period_filters(start: date, end: date | None = None) -> list[Any]:
    filters: list[Any] = [Transaction.booking_date >= start]
    if end is not None:
        filters.append(Transaction.booking_date <= end)
    return filters


def non_transfer_filters(*, include_transfers: bool = False) -> list[Any]:
    return [] if include_transfers else [Transaction.is_transfer.is_(False)]


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

