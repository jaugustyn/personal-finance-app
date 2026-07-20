"""GET /forecast — monthly spending forecast (per category or total)."""
import math
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.errors import not_found, validation_error
from finance.currencies import resolve_base_currency
from finance.db import get_session
from finance.domain.enums import TransactionDirection
from finance.ml.forecasting.pipeline import (
    ForecastDataNotReady,
    forecast_best,
    forecast_readiness,
    load_monthly_series,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])


def _finite_or_none(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None


def _finite_amount(value: float) -> float:
    return value if math.isfinite(value) else 0.0


class HistoryPoint(BaseModel):
    month: date
    amount: float


class ForecastPoint(BaseModel):
    month: date
    amount: float


class ForecastResponse(BaseModel):
    category: str | None
    base_currency: str
    model: str
    horizon: int
    mape: float | None
    rmse: float | None
    validation_folds: int
    baseline_rmse: float | None
    improvement_vs_baseline: float | None
    is_baseline: bool
    history_months: int
    active_months: int
    required_history_months: int
    history: list[HistoryPoint]
    forecast: list[ForecastPoint]


@router.get("", response_model=ForecastResponse)
def forecast(
    session: Session = Depends(get_session),
    category: str | None = Query(default=None),
    horizon: int = Query(default=3, ge=1, le=12),
) -> ForecastResponse:
    series = load_monthly_series(
        session,
        category=category,
        direction=TransactionDirection.DEBIT.value,
    )
    if series.empty:
        raise not_found("No data for given filters")
    readiness = forecast_readiness(series, horizon=horizon)
    try:
        res = forecast_best(series, horizon=horizon)
    except ForecastDataNotReady as exc:
        state = exc.readiness
        raise validation_error(
            {
                "code": "forecast_data_not_ready",
                "history_months": state.history_months,
                "active_months": state.active_months,
                "required_history_months": state.required_history_months,
                "required_active_months": state.required_active_months,
            }
        ) from exc
    return ForecastResponse(
        category=category,
        base_currency=resolve_base_currency(session),
        model=res.name,
        horizon=horizon,
        mape=_finite_or_none(res.mape),
        rmse=_finite_or_none(res.rmse),
        validation_folds=res.validation_folds,
        baseline_rmse=_finite_or_none(res.baseline_rmse),
        improvement_vs_baseline=_finite_or_none(res.improvement_vs_baseline),
        is_baseline=res.is_baseline,
        history_months=readiness.history_months,
        active_months=readiness.active_months,
        required_history_months=readiness.required_history_months,
        history=[
            HistoryPoint(month=ts.date(), amount=_finite_amount(float(v)))
            for ts, v in series.items()
        ],
        forecast=[
            ForecastPoint(month=ts.date(), amount=_finite_amount(float(v)))
            for ts, v in res.forecast.items()
        ],
    )
