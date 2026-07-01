"""Deterministic recommendation tools for the local finance assistant."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import debit_spending_filters, non_transfer_filters
from finance.currencies import amount_base_expr
from finance.domain.models import Transaction
from finance.llm.periods import parse_period
from finance.llm.tool_schemas import SavingsRecommendationsArgs
from finance.llm.types import (
    AnomalySummary,
    CategoryLimitAlert,
    CategoryOpportunity,
    MerchantSpend,
    PeriodRange,
    ProfileSummary,
    SavingsGoalSummary,
    SavingsRecommendationResult,
    SubscriptionSummary,
    ToolResult,
    tool_result,
)
from finance.ml.anomaly.service import list_anomaly_rows
from finance.ml.subscriptions.service import list_subscription_rows
from finance.profile.service import get_or_create_profile
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)


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
    amount_expr = amount_base_expr()
    stmt = (
        select(Transaction.category, func.sum(func.abs(amount_expr)))
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
) -> list[MerchantSpend]:
    amount_expr = amount_base_expr()
    rows = session.execute(
        select(Transaction.merchant, Transaction.title, func.abs(amount_expr)).where(
            *debit_spending_filters(start, end)
        )
    ).all()
    alias_map, label_map = load_merchant_alias_maps(session)
    groups: dict[str, dict[str, Any]] = {}
    for merchant, title, amount in rows:
        identity = merchant_identity(
            merchant,
            title,
            alias_map=alias_map,
            label_map=label_map,
        )
        if not identity.canonical_key:
            continue
        group = groups.setdefault(
            identity.canonical_key,
            {"merchant": identity.display_label, "total": 0.0, "transactions": 0},
        )
        if not group["merchant"]:
            group["merchant"] = merchant_display_label(merchant, title)
        group["total"] += _safe_float(amount)
        group["transactions"] += 1
    sorted_groups = sorted(
        groups.values(),
        key=lambda item: (item["total"], item["transactions"]),
        reverse=True,
    )[:limit]
    return [
        MerchantSpend(
            merchant=str(row["merchant"]),
            total=_safe_float(row["total"]),
            transactions=int(row["transactions"]),
        )
        for row in sorted_groups
    ]


def _income_total(session: Session, start: date, end: date) -> float:
    amount_expr = amount_base_expr()
    stmt = (
        select(func.sum(func.abs(amount_expr)))
        .where(Transaction.direction == "credit")
        .where(*non_transfer_filters())
        .where(Transaction.booking_date >= start)
        .where(Transaction.booking_date <= end)
    )
    return _safe_float(session.execute(stmt).scalar())


def recommend_savings(session: Session, args: dict[str, Any]) -> ToolResult:
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

    category_opportunities: list[CategoryOpportunity] = []
    for category, current_total in current.items():
        previous_total = previous.get(category, 0.0)
        delta = current_total - previous_total
        if delta <= 0:
            continue
        category_opportunities.append(
            CategoryOpportunity(
                kind="category_increase",
                category=category,
                current_total=current_total,
                previous_total=previous_total,
                delta=delta,
                delta_pct=(delta / previous_total * 100.0)
                if previous_total
                else None,
            )
        )
    category_opportunities.sort(key=lambda row: row.delta, reverse=True)

    merchants = _top_merchants(session, start, end, limit=parsed.limit)
    opportunities = category_opportunities[: parsed.limit]
    limits = {
        str(category): _safe_float(limit)
        for category, limit in (profile.category_limits or {}).items()
    }
    limit_alerts = [
        CategoryLimitAlert(
            category=category,
            limit=limit,
            actual=current.get(category, 0.0),
            over_by=current.get(category, 0.0) - limit,
        )
        for category, limit in limits.items()
        if current.get(category, 0.0) > limit
    ]
    limit_alerts.sort(key=lambda row: row.over_by, reverse=True)

    subs = list_subscription_rows(session)
    subscriptions_summary = SubscriptionSummary(
        count=len(subs),
        estimated_monthly_cost=float(
            sum(_safe_float(sub.estimated_monthly_cost) for sub in subs)
        ),
    )
    anomalies = list_anomaly_rows(
        session,
        date_from=start,
        date_to=end,
        direction="debit",
        limit=100,
        mode="review",
        include_model_only=False,
    )
    anomaly_summary = AnomalySummary(
        count=len(anomalies),
        max_severity=max((_safe_float(row.severity) for row in anomalies), default=0.0),
    )

    return tool_result(
        SavingsRecommendationResult(
            period=PeriodRange(start=start.isoformat(), end=end.isoformat()),
            previous_period=PeriodRange(
                start=prev_start.isoformat(),
                end=prev_end.isoformat(),
            ),
            total_current=float(total_current),
            total_previous=float(total_previous),
            delta=float(total_current - total_previous),
            profile=ProfileSummary(
                base_currency=profile.base_currency,
                salary_day=profile.salary_day,
                monthly_savings_goal=monthly_goal if monthly_goal > 0 else None,
                category_limits=limits,
            ),
            savings_goal=SavingsGoalSummary(
                income=float(income_current),
                actual_savings=float(actual_savings),
                target=monthly_goal if monthly_goal > 0 else None,
                remaining=(monthly_goal - actual_savings) if monthly_goal > 0 else None,
                met=actual_savings >= monthly_goal if monthly_goal > 0 else None,
            ),
            category_limit_alerts=limit_alerts,
            category_opportunities=opportunities,
            top_merchants=merchants,
            subscriptions=subscriptions_summary,
            anomalies=anomaly_summary,
        )
    )
