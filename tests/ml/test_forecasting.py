"""Smoke tests for forecasting wrappers + walk-forward CV."""
import numpy as np
import pandas as pd

from finance.ml.forecasting.pipeline import (
    build_monthly_series,
    evaluate_walk_forward,
    forecast_best,
)
from finance.ml.forecasting.registry import (
    MeanForecaster,
    NaiveForecaster,
    SESForecaster,
)


def _make_series(n: int = 9, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-08-01", periods=n, freq="MS")
    base = 1000 + np.arange(n) * 25 + rng.normal(0, 50, size=n)
    return pd.Series(base, index=idx, name="food")


def test_naive_forecaster_predicts_last_value() -> None:
    s = _make_series()
    fc = NaiveForecaster().fit(s).predict(3)
    assert len(fc) == 3
    assert np.isclose(fc.iloc[0], s.iloc[-1])
    assert (fc == fc.iloc[0]).all()


def test_mean_forecaster_uses_window() -> None:
    s = _make_series()
    fc = MeanForecaster(window=3).fit(s).predict(2)
    assert len(fc) == 2
    assert np.isclose(fc.iloc[0], s.tail(3).mean())


def test_ses_forecaster_returns_finite_values() -> None:
    s = _make_series()
    fc = SESForecaster().fit(s).predict(3)
    assert len(fc) == 3
    assert np.isfinite(fc.values).all()


def test_walk_forward_returns_metrics() -> None:
    s = _make_series(n=10, seed=1)
    res = evaluate_walk_forward(s, horizon=1, min_train=4)
    assert "naive" in res
    assert "ses" in res
    for _name, m in res.items():
        assert "rmse" in m and "mape" in m
        assert m["rmse"] >= 0
        assert m["n_folds"] >= 1


def test_forecast_best_picks_a_model() -> None:
    s = _make_series(n=10, seed=2)
    out = forecast_best(s, horizon=3)
    assert out.name in {"naive", "mean3", "ses", "arima"}
    assert len(out.forecast) == 3
    assert np.isfinite(out.forecast.values).all()


def test_forecast_best_clamps_negative_spend_to_zero() -> None:
    idx = pd.date_range("2026-01-01", periods=3, freq="MS")
    series = pd.Series([-100.0, -50.0, -10.0], index=idx, name="food")
    out = forecast_best(series, horizon=2)
    assert (out.forecast >= 0).all()


def test_forecast_best_serializes_nan_mape_as_none() -> None:
    idx = pd.date_range("2026-01-01", periods=6, freq="MS")
    series = pd.Series([0.0] * 6, index=idx, name="food")
    out = forecast_best(series, horizon=2)
    assert out.mape is None


def test_build_monthly_series_aggregates_debits() -> None:
    df = pd.DataFrame({
        "booking_date": ["2026-01-15", "2026-01-20", "2026-02-05", "2026-02-10"],
        "amount": [-30, -20, -100, 5000],  # last one is credit (salary)
        "direction": ["debit", "debit", "debit", "credit"],
        "category": ["food"] * 4,
    })
    s = build_monthly_series(df, category="food", direction="debit")
    assert s.loc["2026-01-01"] == 50.0
    assert s.loc["2026-02-01"] == 100.0  # credit excluded


def test_build_monthly_series_fills_missing_months_and_excludes_non_candidates() -> None:
    df = pd.DataFrame({
        "booking_date": [
            "2026-01-15",
            "2026-03-20",
            "2026-03-21",
            "2026-03-22",
            "2026-03-23",
        ],
        "amount": [-30, -70, -9999, -500, -250],
        "direction": ["debit", "debit", "debit", "debit", "debit"],
        "category": ["food", "food", "food", "food", "food"],
        "is_transfer": [False, "false", True, False, False],
        "transaction_type": [
            "expense",
            "expense",
            "own_transfer",
            "refund",
            "debt_payment",
        ],
    })
    s = build_monthly_series(df, category="food", direction="debit")
    assert s.loc["2026-01-01"] == 30.0
    assert s.loc["2026-02-01"] == 0.0
    assert s.loc["2026-03-01"] == 70.0
