"""Aggregations used by dashboard stats endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import non_transfer_filters
from finance.domain.models import Transaction


def months_ago(months: int) -> date:
    today = date.today()
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _income_expr() -> Any:
    return func.coalesce(
        func.sum(
            case((Transaction.direction == "credit", func.abs(Transaction.amount)), else_=0)
        ),
        0,
    )


def _expense_expr() -> Any:
    return func.coalesce(
        func.sum(
            case((Transaction.direction == "debit", func.abs(Transaction.amount)), else_=0)
        ),
        0,
    )


def _abs_amount_sum() -> Any:
    return func.coalesce(func.sum(func.abs(Transaction.amount)), 0)


def _base_filters(start: date, *, include_transfers: bool) -> list[Any]:
    return [
        Transaction.booking_date >= start,
        *non_transfer_filters(include_transfers=include_transfers),
    ]


def overview(
    session: Session,
    *,
    months: int,
    include_transfers: bool = False,
) -> dict[str, Any]:
    start = months_ago(months - 1)
    stmt = select(
        _income_expr().label("inc"),
        _expense_expr().label("exp"),
        func.count().label("cnt"),
        func.min(Transaction.booking_date).label("dmin"),
        func.max(Transaction.booking_date).label("dmax"),
    ).where(*_base_filters(start, include_transfers=include_transfers))
    row = session.execute(stmt).one()
    income = Decimal(row.inc or 0)
    expenses = Decimal(row.exp or 0)
    net = income - expenses
    savings = float(net / income) if income > 0 else 0.0
    return {
        "period_from": row.dmin,
        "period_to": row.dmax,
        "total_income": income,
        "total_expenses": expenses,
        "net_cashflow": net,
        "savings_rate": max(min(savings, 1.0), -10.0),
        "tx_count": int(row.cnt or 0),
    }


def cashflow(
    session: Session,
    *,
    months: int,
    include_transfers: bool = False,
) -> list[dict[str, Any]]:
    start = months_ago(months - 1)
    bucket = func.to_char(Transaction.booking_date, "YYYY-MM").label("month")
    stmt = (
        select(
            bucket,
            _income_expr().label("inc"),
            _expense_expr().label("exp"),
        )
        .where(*_base_filters(start, include_transfers=include_transfers))
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = session.execute(stmt).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        income = Decimal(row.inc or 0)
        expenses = Decimal(row.exp or 0)
        out.append(
            {
                "month": row.month,
                "income": income,
                "expenses": expenses,
                "net": income - expenses,
            }
        )
    return out


def by_category(
    session: Session,
    *,
    months: int,
    direction: str,
    limit: int,
    include_transfers: bool = False,
    include_predictions: bool = False,
) -> list[dict[str, Any]]:
    start = months_ago(months - 1)
    category = (
        func.coalesce(Transaction.category, Transaction.category_predicted)
        if include_predictions
        else Transaction.category
    )
    amount = _abs_amount_sum().label("amount")
    count = func.count().label("cnt")
    stmt = (
        select(category.label("category"), amount, count)
        .where(*_base_filters(start, include_transfers=include_transfers))
        .where(Transaction.direction == direction)
        .group_by(category)
        .order_by(amount.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    total = sum((Decimal(row.amount or 0) for row in rows), Decimal(0))
    out: list[dict[str, Any]] = []
    for row in rows:
        value = Decimal(row.amount or 0)
        out.append(
            {
                "category": row.category,
                "amount": value,
                "share": float(value / total) if total > 0 else 0.0,
                "count": int(row.cnt),
            }
        )
    return out


def networth(
    session: Session,
    *,
    months: int,
    include_transfers: bool = False,
) -> list[dict[str, Any]]:
    start = months_ago(months - 1)
    bucket = func.to_char(Transaction.booking_date, "YYYY-MM").label("month")
    stmt = (
        select(
            bucket,
            (_income_expr() - _expense_expr()).label("net"),
        )
        .where(*_base_filters(start, include_transfers=include_transfers))
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = session.execute(stmt).all()
    running = Decimal(0)
    out: list[dict[str, Any]] = []
    for row in rows:
        running += Decimal(row.net or 0)
        out.append({"month": row.month, "balance": running})
    return out


def top_merchants(
    session: Session,
    *,
    months: int,
    limit: int,
    direction: str,
    include_transfers: bool = False,
) -> list[dict[str, Any]]:
    start = months_ago(months - 1)
    amount = _abs_amount_sum().label("amount")
    count = func.count().label("cnt")
    stmt = (
        select(Transaction.merchant, amount, count)
        .where(*_base_filters(start, include_transfers=include_transfers))
        .where(Transaction.direction == direction)
        .where(Transaction.merchant != "")
        .group_by(Transaction.merchant)
        .order_by(amount.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [
        {
            "merchant": row.merchant,
            "amount": Decimal(row.amount or 0),
            "count": int(row.cnt),
        }
        for row in rows
    ]

