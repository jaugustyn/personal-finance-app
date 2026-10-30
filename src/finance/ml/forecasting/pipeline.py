"""Forecast pipeline: build monthly series + walk-forward CV."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, TypedDict

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_mask
from finance.currencies import amount_base_expr
from finance.domain.models import Transaction
from finance.ml.forecasting.registry import FORECASTERS, Forecaster
from finance.transactions.type_decision import effective_transaction_type_expr

MIN_HISTORY_MONTHS = 12
MIN_ACTIVE_MONTHS = 6
MIN_TRAIN_MONTHS = 6
MIN_VALIDATION_FOLDS = 6
MIN_COMPLEX_IMPROVEMENT = 0.05
BASELINE_MODELS = frozenset({"naive", "mean3", "ses"})


class ForecastErrors(TypedDict):
    mape: float | None
    rmse: float | None
    n_folds: int


class WalkForwardMetrics(ForecastErrors):
    status: Literal["ok", "insufficient_history", "failed"]
    expected_folds: int
    failed_folds: int
    min_train_months: int
    horizon_metrics: dict[int, ForecastErrors]


@dataclass(frozen=True)
class ForecastReadiness:
    ready: bool
    history_months: int
    active_months: int
    required_history_months: int
    required_active_months: int = MIN_ACTIVE_MONTHS


class ForecastDataNotReady(ValueError):
    def __init__(self, readiness: ForecastReadiness) -> None:
        self.readiness = readiness
        super().__init__(
            "Forecast requires "
            f"{readiness.required_history_months} complete months and activity in "
            f"at least {readiness.required_active_months} months."
        )


@dataclass
class ForecastResult:
    name: str  # forecaster name
    series: pd.Series  # historical (monthly)
    forecast: pd.Series  # predicted values
    mape: float | None = None
    rmse: float | None = None
    validation_folds: int = 0
    baseline_rmse: float | None = None
    improvement_vs_baseline: float | None = None
    is_baseline: bool = True
    validation_metrics: dict[str, WalkForwardMetrics] = field(default_factory=dict)


def required_history_months(
    horizon: int,
    *,
    min_train: int = MIN_TRAIN_MONTHS,
    min_validation_folds: int = MIN_VALIDATION_FOLDS,
) -> int:
    """History needed for six horizon-matched walk-forward folds."""
    return max(
        MIN_HISTORY_MONTHS,
        min_train + horizon + min_validation_folds - 1,
    )


def forecast_readiness(
    series: pd.Series,
    *,
    horizon: int,
    min_train: int = MIN_TRAIN_MONTHS,
    min_validation_folds: int = MIN_VALIDATION_FOLDS,
) -> ForecastReadiness:
    history_months = len(series)
    active_months = int((series > 0).sum())
    required = required_history_months(
        horizon,
        min_train=min_train,
        min_validation_folds=min_validation_folds,
    )
    return ForecastReadiness(
        ready=history_months >= required and active_months >= MIN_ACTIVE_MONTHS,
        history_months=history_months,
        active_months=active_months,
        required_history_months=required,
    )


def build_monthly_series(
    df: pd.DataFrame,
    *,
    category: str | None = None,
    direction: str = "debit",
    exclude_incomplete_month: bool = False,
) -> pd.Series:
    """Aggregate transactions into a monthly absolute-spending series.

    Expects columns: booking_date (datetime-able), abs_amount (or amount),
    direction, category (optional). Category history ends at the last observed
    month of the input, even when the most recent rows belong to other flows.
    """
    if df.empty:
        return pd.Series(dtype=float, name=category or "all")
    d = df.copy()
    d["booking_date"] = pd.to_datetime(d["booking_date"])
    observed_dates = d["booking_date"]
    if exclude_incomplete_month:
        today = pd.Timestamp(date.today())
        observed_dates = observed_dates[observed_dates < today + pd.Timedelta(days=1)]
    if observed_dates.empty:
        return pd.Series(dtype=float, name=category or "all")
    observed_end = observed_dates.max().to_period("M").to_timestamp()
    if exclude_incomplete_month:
        current_month = today.to_period("M").to_timestamp()
        observed_end = min(observed_end, current_month - pd.offsets.MonthBegin(1))
    d = d[expense_category_candidate_mask(d, direction=direction)]
    if category is not None:
        d = d[d["category"] == category]
    if d.empty:
        return pd.Series(dtype=float, name=category or "all")
    if "abs_amount" not in d.columns:
        d["abs_amount"] = d["amount"].abs()
    s = (
        d.set_index("booking_date")["abs_amount"]
        .resample("MS")
        .sum()
        .astype(float)
    )
    if not s.empty:
        idx = pd.date_range(start=s.index.min(), end=observed_end, freq="MS")
        s = s.reindex(idx, fill_value=0.0)
    s.name = category or "all"
    return s


def load_monthly_series(
    session: Session,
    *,
    category: str | None = None,
    direction: str = "debit",
    exclude_incomplete_month: bool = True,
) -> pd.Series:
    stmt = select(
        Transaction.booking_date,
        amount_base_expr().label("amount"),
        Transaction.direction,
        Transaction.category,
        Transaction.is_transfer,
        effective_transaction_type_expr().label("transaction_type"),
    ).where(amount_base_expr().is_not(None))
    rows = session.execute(stmt).all()
    df = pd.DataFrame(
        rows,
        columns=[
            "booking_date",
            "amount",
            "direction",
            "category",
            "is_transfer",
            "transaction_type",
        ],
    )
    if df.empty:
        return pd.Series(dtype=float, name=category or "all")
    df["abs_amount"] = df["amount"].abs().astype(float)
    return build_monthly_series(
        df,
        category=category,
        direction=direction,
        exclude_incomplete_month=exclude_incomplete_month,
    )


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    eps = 1e-9
    mask = np.abs(y_true) > eps
    if mask.sum() == 0:
        return None
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _fit_predict(model: Forecaster, train: pd.Series, horizon: int) -> pd.Series:
    """Apply the same spending constraints in validation and the final forecast."""
    model.fit(train)
    forecast = model.predict(horizon).astype(float)
    expected_index = pd.date_range(
        train.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS",
    )
    if not forecast.index.equals(expected_index) or not np.isfinite(forecast.to_numpy()).all():
        raise ValueError("Forecaster returned invalid dates or non-finite amounts.")
    return forecast.clip(lower=0.0)


def evaluate_walk_forward(
    series: pd.Series,
    *,
    horizon: int = 1,
    min_train: int = MIN_TRAIN_MONTHS,
    min_validation_folds: int = MIN_VALIDATION_FOLDS,
) -> dict[str, WalkForwardMetrics]:
    """Compare eligible models on identical expanding-window origins.

    A model must complete every scheduled fold to receive a comparable score.
    History requirements are checked before fitting, including the seasonal
    model's two full years. Errors are also reported separately for steps 1..h.
    """
    n = len(series)
    if n < min_train + horizon:
        return {}

    train_sizes = {
        name: max(min_train, factory().min_history)
        for name, factory in FORECASTERS.items()
    }
    eligible = {
        name for name, size in train_sizes.items()
        if n - size - horizon + 1 >= min_validation_folds
    }
    common_start = max((train_sizes[name] for name in eligible), default=min_train)
    splits = range(common_start, n - horizon + 1)
    results: dict[str, WalkForwardMetrics] = {}
    for name, factory in FORECASTERS.items():
        metrics: WalkForwardMetrics = {
            "status": "insufficient_history",
            "mape": None,
            "rmse": None,
            "n_folds": 0,
            "expected_folds": len(splits) if name in eligible else 0,
            "failed_folds": 0,
            "min_train_months": common_start if name in eligible else train_sizes[name],
            "horizon_metrics": {},
        }
        results[name] = metrics
        if name not in eligible:
            continue
        truths: list[np.ndarray] = []
        preds: list[np.ndarray] = []
        for split in splits:
            train = series.iloc[:split]
            test = series.iloc[split:split + horizon]
            try:
                fc = _fit_predict(factory(), train, horizon)
            except Exception:
                metrics["failed_folds"] += 1
                continue
            truths.append(test.to_numpy(dtype=float))
            preds.append(fc.to_numpy(dtype=float))
        metrics["n_folds"] = len(truths)
        if metrics["failed_folds"]:
            metrics["status"] = "failed"
            logging.getLogger(__name__).warning(
                "Forecast validation failed for %s in %s/%s folds; candidate excluded.",
                name, metrics["failed_folds"], metrics["expected_folds"],
            )
            continue
        yt = np.asarray(truths)
        yp = np.asarray(preds)
        metrics["status"] = "ok"
        metrics["mape"] = _mape(yt, yp)
        metrics["rmse"] = _rmse(yt, yp)
        metrics["horizon_metrics"] = {
            step + 1: {
                "mape": _mape(yt[:, step], yp[:, step]),
                "rmse": _rmse(yt[:, step], yp[:, step]),
                "n_folds": len(truths),
            }
            for step in range(horizon)
        }
    return results


def forecast_best(
    series: pd.Series,
    horizon: int = 3,
    *,
    min_train: int = MIN_TRAIN_MONTHS,
    min_validation_folds: int = MIN_VALIDATION_FOLDS,
) -> ForecastResult:
    """Select a model using horizon-matched walk-forward validation."""
    readiness = forecast_readiness(
        series,
        horizon=horizon,
        min_train=min_train,
        min_validation_folds=min_validation_folds,
    )
    if not readiness.ready:
        raise ForecastDataNotReady(readiness)

    cv = evaluate_walk_forward(
        series, horizon=horizon, min_train=min_train,
        min_validation_folds=min_validation_folds,
    )
    eligible = {
        name: metrics["rmse"]
        for name, metrics in cv.items()
        if metrics["status"] == "ok"
        and metrics["n_folds"] >= min_validation_folds
        and metrics["rmse"] is not None
    }
    baseline_candidates = {
        name: metrics
        for name, metrics in eligible.items()
        if name in BASELINE_MODELS
    }
    if not baseline_candidates:
        raise ForecastDataNotReady(readiness)

    baseline = min(
        baseline_candidates,
        key=baseline_candidates.__getitem__,
    )
    chosen = min(eligible, key=eligible.__getitem__)
    baseline_rmse = baseline_candidates[baseline]
    chosen_rmse = eligible[chosen]
    improvement = (
        (baseline_rmse - chosen_rmse) / baseline_rmse
        if baseline_rmse > 0
        else 0.0
    )
    if chosen not in BASELINE_MODELS and improvement < MIN_COMPLEX_IMPROVEMENT:
        chosen = baseline
        improvement = 0.0

    fc = _fit_predict(FORECASTERS[chosen](), series, horizon)
    return ForecastResult(
        name=chosen,
        series=series,
        forecast=fc,
        mape=cv[chosen]["mape"],
        rmse=eligible[chosen],
        validation_folds=cv[chosen]["n_folds"],
        baseline_rmse=baseline_rmse,
        improvement_vs_baseline=float(improvement),
        is_baseline=chosen in BASELINE_MODELS,
        validation_metrics=cv,
    )
