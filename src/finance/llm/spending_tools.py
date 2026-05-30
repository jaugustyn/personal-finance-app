"""Spending and comparison function-calling tools."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import debit_spending_filters
from finance.domain.models import Transaction
from finance.llm.periods import parse_period
from finance.llm.tool_schemas import ComparePeriodsArgs, GetSpendingArgs, TopMerchantsArgs


def get_spending(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = GetSpendingArgs(**args)
    start, end = parse_period(parsed.period)
    stmt = (
        select(func.sum(func.abs(Transaction.amount)), func.count())
        .where(*debit_spending_filters(start, end, category=parsed.category))
    )
    total, n = session.execute(stmt).one()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "category": parsed.category,
        "total": float(total or 0.0),
        "transactions": int(n or 0),
    }


def top_merchants(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = TopMerchantsArgs(**args)
    start, end = parse_period(parsed.period)
    stmt = (
        select(
            Transaction.merchant,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count().label("n"),
        )
        .where(*debit_spending_filters(start, end, category=parsed.category))
        .group_by(Transaction.merchant)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .limit(parsed.limit)
    )
    rows = session.execute(stmt).all()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "category": parsed.category,
        "merchants": [
            {"merchant": m or "", "total": float(t or 0.0), "transactions": int(n)}
            for m, t, n in rows
        ],
    }


def compare_periods(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ComparePeriodsArgs(**args)
    a_start, a_end = parse_period(parsed.period_a)
    b_start, b_end = parse_period(parsed.period_b)

    def _sum(start: date, end: date) -> float:
        stmt = (
            select(func.sum(func.abs(Transaction.amount)))
            .where(*debit_spending_filters(start, end, category=parsed.category))
        )
        return float(session.execute(stmt).scalar() or 0.0)

    total_a, total_b = _sum(a_start, a_end), _sum(b_start, b_end)
    delta = total_a - total_b
    pct = (delta / total_b * 100.0) if total_b else None
    return {
        "category": parsed.category,
        "a": {"start": a_start.isoformat(), "end": a_end.isoformat(), "total": total_a},
        "b": {"start": b_start.isoformat(), "end": b_end.isoformat(), "total": total_b},
        "delta": delta,
        "delta_pct": pct,
    }
