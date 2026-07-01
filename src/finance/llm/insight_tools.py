"""Subscription, anomaly and forecast assistant tools."""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from finance.llm.periods import parse_period
from finance.llm.tool_schemas import ForecastArgs, ListAnomaliesArgs, ListSubscriptionsArgs
from finance.llm.types import (
    AnomalyToolItem,
    ForecastPoint,
    ForecastResult,
    ListAnomaliesResult,
    ListSubscriptionsResult,
    PeriodRange,
    SubscriptionToolItem,
    ToolResult,
    tool_result,
)
from finance.ml.anomaly import service as anomaly_service
from finance.ml.forecasting.pipeline import forecast_best, load_monthly_series
from finance.ml.subscriptions import service as subscription_service


def _safe_float(value: object, *, default: float | None = 0.0) -> float | None:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def list_subscriptions(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = ListSubscriptionsArgs(**args)
    subs = subscription_service.list_subscription_rows(
        session,
        min_confidence=parsed.min_confidence,
    )
    out = [
        SubscriptionToolItem(
            merchant=sub.display_name,
            status=sub.status,
            cadence=sub.cadence,
            median_amount=_safe_float(sub.median_amount),
            occurrences=int(sub.occurrences),
            confidence=_safe_float(sub.confidence),
            estimated_monthly_cost=_safe_float(sub.estimated_monthly_cost),
        )
        for sub in subs
    ]
    monthly_cost = sum(float(sub.estimated_monthly_cost or 0.0) for sub in out)
    return tool_result(
        ListSubscriptionsResult(
            subscriptions=out,
            estimated_monthly_cost=float(monthly_cost),
        )
    )


def list_anomalies(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = ListAnomaliesArgs(**args)
    start, end = parse_period(parsed.period)
    rows = anomaly_service.list_anomaly_rows(
        session,
        date_from=start,
        date_to=end,
        direction="debit",
        limit=parsed.limit,
        mode="review",
        include_model_only=False,
    )
    out: list[AnomalyToolItem] = []
    for row in rows:
        out.append(
            AnomalyToolItem(
                id=row.id,
                booking_date=row.booking_date.isoformat(),
                merchant=row.merchant,
                amount=_safe_float(row.amount),
                severity=_safe_float(row.severity),
                priority_score=_safe_float(row.priority_score),
                anomaly_type=row.anomaly_type,
                reasons=row.reasons,
                feedback_status=row.feedback_status,
            )
        )
    return tool_result(
        ListAnomaliesResult(
            period=PeriodRange(start=start.isoformat(), end=end.isoformat()),
            anomalies=out,
        )
    )


def forecast_for(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = ForecastArgs(**args)
    series = load_monthly_series(session, category=parsed.category, direction="debit")
    if series.empty:
        return tool_result(ForecastResult(category=parsed.category, error="no data"))
    result = forecast_best(series, horizon=parsed.horizon)
    return tool_result(
        ForecastResult(
            category=parsed.category,
            model=result.name,
            mape=_safe_float(result.mape, default=None),
            rmse=_safe_float(result.rmse, default=None),
            forecast=[
                ForecastPoint(month=ts.date().isoformat(), amount=_safe_float(value))
                for ts, value in result.forecast.items()
            ],
        )
    )
