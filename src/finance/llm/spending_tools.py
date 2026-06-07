"""Spending and comparison function-calling tools."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import (
    category_candidate_type_filter,
    debit_spending_filters,
    non_transfer_filters,
    period_filters,
)
from finance.domain.models import Transaction
from finance.llm.periods import parse_period
from finance.llm.tool_schemas import (
    CashflowOverviewArgs,
    ComparePeriodsArgs,
    GetSpendingArgs,
    TopCategoriesArgs,
    TopMerchantsArgs,
)


def _category_candidate_type_filter():
    return category_candidate_type_filter()


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


def top_categories(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = TopCategoriesArgs(**args)
    start, end = parse_period(parsed.period)
    base_filters = [
        *debit_spending_filters(start, end),
        _category_candidate_type_filter(),
    ]
    total_stmt = select(
        func.sum(func.abs(Transaction.amount)),
        func.count(),
    ).where(*base_filters)
    total, tx_count = session.execute(total_stmt).one()
    total_candidate_spend = float(total or 0.0)

    rows = session.execute(
        select(
            Transaction.category,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count().label("n"),
        )
        .where(*base_filters, Transaction.category.is_not(None))
        .group_by(Transaction.category)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
    ).all()
    categorized_total = float(sum(float(total or 0.0) for _, total, _ in rows))
    uncategorized_total = max(total_candidate_spend - categorized_total, 0.0)
    category_coverage = (
        categorized_total / total_candidate_spend if total_candidate_spend else 0.0
    )

    categories = []
    for category, category_total, n in rows[: parsed.limit]:
        value = float(category_total or 0.0)
        categories.append(
            {
                "category": category,
                "total": value,
                "transactions": int(n or 0),
                "share": value / total_candidate_spend
                if total_candidate_spend
                else 0.0,
            }
        )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_candidate_spend": total_candidate_spend,
        "categorized_total": categorized_total,
        "uncategorized_total": uncategorized_total,
        "category_coverage": category_coverage,
        "transactions": int(tx_count or 0),
        "categories": categories,
    }


def cashflow_overview(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = CashflowOverviewArgs(**args)
    start, end = parse_period(parsed.period)
    income_expr = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "credit", func.abs(Transaction.amount)),
                else_=0,
            )
        ),
        0,
    )
    expense_expr = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "debit", func.abs(Transaction.amount)),
                else_=0,
            )
        ),
        0,
    )
    row = session.execute(
        select(
            income_expr.label("income"),
            expense_expr.label("expenses"),
            func.count().label("tx_count"),
        ).where(
            *period_filters(start, end),
            *non_transfer_filters(),
        )
    ).one()
    income = float(row.income or 0.0)
    expenses = float(row.expenses or 0.0)
    net = income - expenses
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "income": income,
        "expenses": expenses,
        "net": net,
        "savings_rate": net / income if income else 0.0,
        "transactions": int(row.tx_count or 0),
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
