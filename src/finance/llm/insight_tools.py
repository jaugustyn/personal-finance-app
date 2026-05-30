"""Subscription, anomaly and forecast assistant tools."""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from finance.llm.periods import parse_period
from finance.llm.tool_data import load_transactions_df
from finance.llm.tool_schemas import ForecastArgs, ListAnomaliesArgs, ListSubscriptionsArgs
from finance.ml.anomaly.detector import detect_anomalies
from finance.ml.forecasting.pipeline import forecast_best, load_monthly_series
from finance.ml.subscriptions.detector import detect_subscriptions


def _safe_float(value: object, *, default: float | None = 0.0) -> float | None:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _split_reasons(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def list_subscriptions(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ListSubscriptionsArgs(**args)
    df = load_transactions_df(session)
    if df.empty:
        return {"subscriptions": []}
    subs = detect_subscriptions(df)
    out: list[dict[str, Any]] = [
        {
            "merchant": sub.merchant,
            "cadence": sub.cadence,
            "median_amount": _safe_float(sub.median_amount),
            "occurrences": int(sub.occurrences),
            "confidence": _safe_float(sub.confidence),
            "estimated_monthly_cost": _safe_float(sub.estimated_monthly_cost),
        }
        for sub in subs
        if sub.confidence >= parsed.min_confidence
    ]
    monthly_cost = sum(
        float(sub.get("estimated_monthly_cost") or 0.0)
        for sub in out
    )
    return {"subscriptions": out, "estimated_monthly_cost": float(monthly_cost)}


def list_anomalies(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ListAnomaliesArgs(**args)
    start, end = parse_period(parsed.period)
    df = load_transactions_df(session)
    if df.empty:
        return {"anomalies": []}
    df = df[(df["booking_date"] >= start) & (df["booking_date"] <= end)]
    if df.empty:
        return {"anomalies": []}
    result = detect_anomalies(df, direction="debit")
    flagged = (
        result.df[result.df["anomaly"]]
        .sort_values("severity", ascending=False)
        .head(parsed.limit)
    )
    out = []
    for _, row in flagged.iterrows():
        booking_date = row["booking_date"]
        booking_iso = (
            booking_date.isoformat()
            if hasattr(booking_date, "isoformat")
            else str(booking_date)
        )
        out.append(
            {
                "id": int(row["id"]),
                "booking_date": booking_iso,
                "merchant": row.get("merchant") or "",
                "amount": _safe_float(row["amount"]),
                "severity": _safe_float(row["severity"]),
                "reasons": _split_reasons(row.get("reasons")),
            }
        )
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "anomalies": out,
    }


def forecast_for(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ForecastArgs(**args)
    series = load_monthly_series(session, category=parsed.category, direction="debit")
    if series.empty:
        return {"category": parsed.category, "error": "no data"}
    result = forecast_best(series, horizon=parsed.horizon)
    return {
        "category": parsed.category,
        "model": result.name,
        "mape": _safe_float(result.mape, default=None),
        "rmse": _safe_float(result.rmse, default=None),
        "forecast": [
            {"month": ts.date().isoformat(), "amount": _safe_float(value)}
            for ts, value in result.forecast.items()
        ],
    }
