"""GET /forecast — monthly spending forecast (per category or total)."""
import math
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.errors import not_found
from finance.db import get_session
from finance.domain.enums import TransactionDirection
from finance.ml.forecasting.pipeline import forecast_best, load_monthly_series

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
    model: str
    horizon: int
    mape: float | None
    rmse: float | None
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
    res = forecast_best(series, horizon=horizon)
    return ForecastResponse(
        category=category,
        model=res.name,
        horizon=horizon,
        mape=_finite_or_none(res.mape),
        rmse=_finite_or_none(res.rmse),
        history=[
            HistoryPoint(month=ts.date(), amount=_finite_amount(float(v)))
            for ts, v in series.items()
        ],
        forecast=[
            ForecastPoint(month=ts.date(), amount=_finite_amount(float(v)))
            for ts, v in res.forecast.items()
        ],
    )
