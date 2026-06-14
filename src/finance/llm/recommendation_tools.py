"""Deterministic recommendation tools for the local finance assistant."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import debit_spending_filters, non_transfer_filters
from finance.domain.models import Transaction
from finance.llm.periods import parse_period
from finance.llm.tool_schemas import SavingsRecommendationsArgs
from finance.ml.anomaly.service import list_anomaly_rows
from finance.ml.subscriptions.service import list_subscription_rows
from finance.profile.service import get_or_create_profile


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _previous_period(start: date, end: date) -> tuple[date, date]:
    days = max((end - start).days + 1, 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return prev_start, prev_end


def _category_totals(session: Session, start: date, end: date) -> dict[str, float]:
    stmt = (
        select(Transaction.category, func.sum(func.abs(Transaction.amount)))
        .where(*debit_spending_filters(start, end))
        .where(Transaction.category.is_not(None))
        .group_by(Transaction.category)
    )
    return {str(category): _safe_float(total) for category, total in session.execute(stmt)}


def _top_merchants(
    session: Session,
    start: date,
    end: date,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            Transaction.merchant,
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count().label("tx_count"),
        )
        .where(*debit_spending_filters(start, end))
        .group_by(Transaction.merchant)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .limit(limit)
    )
    return [
        {
            "merchant": merchant or "(brak nazwy)",
            "total": _safe_float(total),
            "transactions": int(count or 0),
        }
        for merchant, total, count in session.execute(stmt)
    ]


def _income_total(session: Session, start: date, end: date) -> float:
    stmt = (
        select(func.sum(func.abs(Transaction.amount)))
        .where(Transaction.direction == "credit")
        .where(*non_transfer_filters())
        .where(Transaction.booking_date >= start)
        .where(Transaction.booking_date <= end)
    )
    return _safe_float(session.execute(stmt).scalar())


def recommend_savings(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic savings opportunities for a period.

    The LLM may explain these facts later, but the numbers are computed here.
    """
    parsed = SavingsRecommendationsArgs(**args)
    start, end = parse_period(parsed.period)
    prev_start, prev_end = _previous_period(start, end)

    current = _category_totals(session, start, end)
    previous = _category_totals(session, prev_start, prev_end)
    total_current = sum(current.values())
    total_previous = sum(previous.values())
    profile = get_or_create_profile(session)
    income_current = _income_total(session, start, end)
    actual_savings = income_current - total_current
    monthly_goal = _safe_float(profile.monthly_savings_goal, default=0.0)

    category_opportunities: list[dict[str, Any]] = []
    for category, current_total in current.items():
        previous_total = previous.get(category, 0.0)
        delta = current_total - previous_total
        if delta <= 0:
            continue
        category_opportunities.append(
            {
                "kind": "category_increase",
                "category": category,
                "current_total": current_total,
                "previous_total": previous_total,
                "delta": delta,
                "delta_pct": (delta / previous_total * 100.0)
                if previous_total
                else None,
            }
        )
    category_opportunities.sort(key=lambda row: row["delta"], reverse=True)

    merchants = _top_merchants(session, start, end, limit=parsed.limit)
    opportunities = category_opportunities[: parsed.limit]
    limits = {
        str(category): _safe_float(limit)
        for category, limit in (profile.category_limits or {}).items()
    }
    limit_alerts: list[dict[str, Any]] = [
        {
            "category": category,
            "limit": limit,
            "actual": current.get(category, 0.0),
            "over_by": current.get(category, 0.0) - limit,
        }
        for category, limit in limits.items()
        if current.get(category, 0.0) > limit
    ]
    limit_alerts.sort(key=lambda row: row["over_by"], reverse=True)

    subscriptions_summary = {"count": 0, "estimated_monthly_cost": 0.0}
    anomaly_summary = {"count": 0, "max_severity": 0.0}
    subs = list_subscription_rows(session)
    subscriptions_summary = {
        "count": len(subs),
        "estimated_monthly_cost": float(
            sum(_safe_float(sub.estimated_monthly_cost) for sub in subs)
        ),
    }
    anomalies = list_anomaly_rows(
        session,
        date_from=start,
        date_to=end,
        direction="debit",
        limit=100,
        mode="review",
        include_model_only=False,
    )
    anomaly_summary = {
        "count": len(anomalies),
        "max_severity": max((_safe_float(row.severity) for row in anomalies), default=0.0),
    }

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "previous_period": {
            "start": prev_start.isoformat(),
            "end": prev_end.isoformat(),
        },
        "total_current": float(total_current),
        "total_previous": float(total_previous),
        "delta": float(total_current - total_previous),
        "profile": {
            "base_currency": profile.base_currency,
            "salary_day": profile.salary_day,
            "monthly_savings_goal": monthly_goal if monthly_goal > 0 else None,
            "category_limits": limits,
        },
        "savings_goal": {
            "income": float(income_current),
            "actual_savings": float(actual_savings),
            "target": monthly_goal if monthly_goal > 0 else None,
            "remaining": (monthly_goal - actual_savings) if monthly_goal > 0 else None,
            "met": actual_savings >= monthly_goal if monthly_goal > 0 else None,
        },
        "category_limit_alerts": limit_alerts,
        "category_opportunities": opportunities,
        "top_merchants": merchants,
        "subscriptions": subscriptions_summary,
        "anomalies": anomaly_summary,
    }
