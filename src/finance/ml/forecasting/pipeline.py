"""Forecast pipeline: build monthly series + walk-forward CV."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_mask
from finance.currencies import amount_base_expr
from finance.domain.models import Transaction
from finance.ml.forecasting.registry import FORECASTERS


@dataclass
class ForecastResult:
    name: str  # forecaster name
    series: pd.Series  # historical (monthly)
    forecast: pd.Series  # predicted values
    mape: float | None = None
    rmse: float | None = None


def build_monthly_series(
    df: pd.DataFrame,
    *,
    category: str | None = None,
    direction: str = "debit",
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
    s.name = category or "all"
    return s


def load_monthly_series(
    session: Session,
    *,
    category: str | None = None,
    direction: str = "debit",
) -> pd.Series:
    stmt = select(
        Transaction.booking_date,
        amount_base_expr().label("amount"),
        Transaction.direction,
        Transaction.category,
        Transaction.is_transfer,
        Transaction.transaction_type,
    )
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
    return build_monthly_series(df, category=category, direction=direction)


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
    min_train: int = 4,
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
    min_train: int = 4,
) -> ForecastResult:
    """Pick the lowest-RMSE model on walk-forward CV, refit on full series."""
    cv = evaluate_walk_forward(series, horizon=1, min_train=min_train)
    if not cv:
        # Too short — use Naive.
        chosen = "naive"
        mape = rmse = None
    else:
        chosen = min(cv.keys(), key=lambda k: cv[k]["rmse"])
        mape = cv[chosen]["mape"]
        rmse = cv[chosen]["rmse"]
    model = FORECASTERS[chosen]()
    model.fit(series)
    fc = model.predict(horizon).astype(float).clip(lower=0.0)
    fc = fc.where(np.isfinite(fc), 0.0)
    mape = mape if mape is not None and np.isfinite(mape) else None
    rmse = rmse if rmse is not None and np.isfinite(rmse) else None
    return ForecastResult(name=chosen, series=series, forecast=fc, mape=mape, rmse=rmse)
