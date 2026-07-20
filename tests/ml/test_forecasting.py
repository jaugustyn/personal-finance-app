"""Smoke tests for forecasting wrappers + walk-forward CV."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from finance.ml.forecasting.pipeline import (
    ForecastDataNotReady,
    build_monthly_series,
    evaluate_walk_forward,
    forecast_best,
    required_history_months,
)
from finance.ml.forecasting.registry import (
    HoltDampedForecaster,
    MeanForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
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


def test_holt_damped_forecaster_preserves_a_visible_trend() -> None:
    s = _make_series(n=18, seed=3)
    fc = HoltDampedForecaster().fit(s).predict(3)
    assert np.isfinite(fc.values).all()
    assert fc.nunique() > 1


def test_seasonal_naive_repeats_previous_year() -> None:
    idx = pd.date_range("2023-01-01", periods=36, freq="MS")
    values = np.tile(np.arange(100.0, 1300.0, 100.0), 3)
    s = pd.Series(values, index=idx)
    fc = SeasonalNaiveForecaster().fit(s).predict(3)
    assert fc.tolist() == [100.0, 200.0, 300.0]


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
    s = _make_series(n=24, seed=2)
    out = forecast_best(s, horizon=3)
    assert out.name in {
        "naive",
        "mean3",
        "ses",
        "holt_damped",
        "seasonal_naive",
    }
    assert len(out.forecast) == 3
    assert np.isfinite(out.forecast.values).all()
    assert out.validation_folds >= 6


def test_forecast_best_uses_trend_only_when_it_beats_baseline() -> None:
    idx = pd.date_range("2024-01-01", periods=24, freq="MS")
    trend = pd.Series(1000.0 + np.arange(24) * 100.0, index=idx)
    trend_result = forecast_best(trend, horizon=3)
    assert trend_result.is_baseline is False
    assert (trend_result.improvement_vs_baseline or 0.0) >= 0.05

    flat = pd.Series([1000.0] * 24, index=idx)
    flat_result = forecast_best(flat, horizon=3)
    assert flat_result.is_baseline is True
    assert flat_result.improvement_vs_baseline == 0.0


def test_forecast_best_clamps_negative_spend_to_zero() -> None:
    idx = pd.date_range("2025-01-01", periods=14, freq="MS")
    series = pd.Series(np.linspace(100.0, 1.0, 14), index=idx, name="food")
    out = forecast_best(series, horizon=2)
    assert (out.forecast >= 0).all()


def test_forecast_best_requires_enough_complete_and_active_months() -> None:
    idx = pd.date_range("2025-01-01", periods=13, freq="MS")
    too_short = pd.Series([100.0] * 13, index=idx, name="food")
    with pytest.raises(ForecastDataNotReady) as exc_info:
        forecast_best(too_short, horizon=3)
    assert exc_info.value.readiness.required_history_months == 14

    inactive = pd.Series(
        [100.0, 0.0, 0.0, 0.0, 0.0, 0.0] * 3,
        index=pd.date_range("2024-01-01", periods=18, freq="MS"),
    )
    with pytest.raises(ForecastDataNotReady):
        forecast_best(inactive, horizon=3)


def test_required_history_grows_with_horizon() -> None:
    assert required_history_months(1) == 12
    assert required_history_months(3) == 14
    assert required_history_months(12) == 23


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


def test_build_monthly_series_excludes_incomplete_current_month() -> None:
    current_month = pd.Timestamp(date.today()).to_period("M").to_timestamp()
    previous_month = current_month - pd.offsets.MonthBegin(1)
    df = pd.DataFrame(
        {
            "booking_date": [
                previous_month + pd.Timedelta(days=5),
                current_month + pd.Timedelta(days=5),
            ],
            "amount": [-100.0, -200.0],
            "direction": ["debit", "debit"],
            "category": ["food", "food"],
        }
    )
    s = build_monthly_series(
        df,
        category="food",
        exclude_incomplete_month=True,
    )
    assert s.index.tolist() == [previous_month]
    assert s.iloc[0] == 100.0
