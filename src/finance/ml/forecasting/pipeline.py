"""Forecast pipeline: build monthly series + walk-forward CV."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_mask
from finance.currencies import amount_base_expr
from finance.domain.models import Transaction
from finance.ml.forecasting.registry import FORECASTERS
from finance.transactions.type_decision import effective_transaction_type_expr

MIN_HISTORY_MONTHS = 12
MIN_ACTIVE_MONTHS = 6
MIN_TRAIN_MONTHS = 6
MIN_VALIDATION_FOLDS = 6
MIN_COMPLEX_IMPROVEMENT = 0.05
BASELINE_MODELS = frozenset({"naive", "mean3", "ses"})


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
    direction, category (optional).
    """
    d = df.copy()
    d["booking_date"] = pd.to_datetime(d["booking_date"])
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
        idx = pd.date_range(start=s.index.min(), end=s.index.max(), freq="MS")
        s = s.reindex(idx, fill_value=0.0)
    if exclude_incomplete_month and not s.empty:
        current_month = pd.Timestamp(date.today()).to_period("M").to_timestamp()
        s = s[s.index < current_month]
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


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    eps = 1e-9
    mask = np.abs(y_true) > eps
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def evaluate_walk_forward(
    series: pd.Series,
    *,
    horizon: int = 1,
    min_train: int = MIN_TRAIN_MONTHS,
) -> dict[str, dict[str, float]]:
    """Walk-forward CV over the series. For each fold trains on [0:t),
    forecasts h steps, compares to the truth at [t:t+h).
    """
    n = len(series)
    if n < min_train + horizon:
        return {}

    results: dict[str, dict[str, float]] = {}
    for name, factory in FORECASTERS.items():
        truths: list[float] = []
        preds: list[float] = []
        for split in range(min_train, n - horizon + 1):
            train = series.iloc[:split]
            test = series.iloc[split:split + horizon]
            try:
                model = factory()
                model.fit(train)
                fc = model.predict(horizon)
            except Exception:
                continue
            truths.extend(test.values.tolist())
            preds.extend(fc.values.tolist())
        if not truths:
            continue
        yt = np.asarray(truths)
        yp = np.asarray(preds)
        results[name] = {
            "mape": _mape(yt, yp),
            "rmse": _rmse(yt, yp),
            "n_folds": int(len(truths) / horizon),
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

    cv = evaluate_walk_forward(series, horizon=horizon, min_train=min_train)
    eligible = {
        name: metrics
        for name, metrics in cv.items()
        if metrics["n_folds"] >= min_validation_folds
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
        key=lambda name: baseline_candidates[name]["rmse"],
    )
    chosen = min(eligible, key=lambda name: eligible[name]["rmse"])
    baseline_rmse = float(baseline_candidates[baseline]["rmse"])
    chosen_rmse = float(eligible[chosen]["rmse"])
    improvement = (
        (baseline_rmse - chosen_rmse) / baseline_rmse
        if baseline_rmse > 0
        else 0.0
    )
    if chosen not in BASELINE_MODELS and improvement < MIN_COMPLEX_IMPROVEMENT:
        chosen = baseline
        improvement = 0.0

    raw_mape = eligible[chosen]["mape"]
    raw_rmse = eligible[chosen]["rmse"]
    model = FORECASTERS[chosen]()
    model.fit(series)
    fc = model.predict(horizon).astype(float).clip(lower=0.0)
    fc = fc.where(np.isfinite(fc), 0.0)
    mape: float | None = float(raw_mape) if np.isfinite(raw_mape) else None
    rmse: float | None = float(raw_rmse) if np.isfinite(raw_rmse) else None
    return ForecastResult(
        name=chosen,
        series=series,
        forecast=fc,
        mape=mape,
        rmse=rmse,
        validation_folds=int(eligible[chosen]["n_folds"]),
        baseline_rmse=baseline_rmse,
        improvement_vs_baseline=float(improvement),
        is_baseline=chosen in BASELINE_MODELS,
    )
