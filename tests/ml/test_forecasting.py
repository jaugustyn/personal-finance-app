"""Smoke tests for forecasting wrappers + walk-forward CV."""
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from finance.ml.forecasting import pipeline as forecast_pipeline
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
    selected = forecast_best(s, horizon=3)
    assert selected.name == "seasonal_naive"
    assert selected.validation_folds == 10
    assert selected.rmse == 0.0


def test_walk_forward_returns_metrics() -> None:
    s = _make_series(n=10, seed=1)
    res = evaluate_walk_forward(s, horizon=1, min_train=4)
    assert "naive" in res
    assert "ses" in res
    assert res["seasonal_naive"]["status"] == "insufficient_history"
    for m in res.values():
        if m["status"] != "ok":
            assert m["rmse"] is None
            continue
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


@pytest.mark.parametrize("months, expected_start", [(31, 6), (36, 24)])
def test_walk_forward_uses_common_origins_for_all_eligible_models(months, expected_start) -> None:
    metrics = evaluate_walk_forward(_make_series(n=months), horizon=3)
    valid = [item for item in metrics.values() if item["status"] == "ok"]

    assert len(valid) == (4 if months == 31 else 5)
    assert {item["min_train_months"] for item in valid} == {expected_start}
    assert {item["n_folds"] for item in valid} == {months - expected_start - 3 + 1}
    assert all(item["n_folds"] == item["expected_folds"] for item in valid)
    assert all(item["failed_folds"] == 0 for item in valid)


def test_walk_forward_fits_identical_training_windows_and_reports_each_horizon(monkeypatch) -> None:
    fitted = {"naive": [], "long_history": []}

    class RecordingNaive(NaiveForecaster):
        def fit(self, train):
            fitted["naive"].append(len(train))
            return super().fit(train)

    class LongHistory(NaiveForecaster):
        min_history = 10

        def fit(self, train):
            fitted["long_history"].append(len(train))
            return super().fit(train)

    monkeypatch.setattr(forecast_pipeline, "FORECASTERS", {
        "naive": RecordingNaive, "long_history": LongHistory,
    })
    series = pd.Series(np.arange(1.0, 21.0), index=pd.date_range("2023-01-01", periods=20, freq="MS"))
    metrics = evaluate_walk_forward(series, horizon=3)

    assert fitted["naive"] == fitted["long_history"] == list(range(10, 18))
    for item in metrics.values():
        assert item["rmse"] == pytest.approx(np.sqrt(14 / 3))
        assert item["n_folds"] == 8
        assert set(item["horizon_metrics"]) == {1, 2, 3}
        for step, errors in item["horizon_metrics"].items():
            assert errors["rmse"] == pytest.approx(step)
            assert errors["n_folds"] == 8


def test_model_with_a_failed_fold_cannot_win_on_remaining_easy_folds(monkeypatch) -> None:
    class SelectivelyFailing(NaiveForecaster):
        def fit(self, train):
            if len(train) == 6:
                raise ValueError("Synthetic fitting failure")
            return super().fit(train)

        def predict(self, horizon):
            forecast = super().predict(horizon)
            return forecast + np.arange(1, horizon + 1)

    monkeypatch.setattr(forecast_pipeline, "FORECASTERS", {
        "naive": NaiveForecaster, "holt_damped": SelectivelyFailing,
    })
    series = pd.Series(np.arange(1.0, 21.0), index=pd.date_range("2023-01-01", periods=20, freq="MS"))

    result = forecast_best(series, horizon=3)

    assert result.name == "naive"
    failed = result.validation_metrics["holt_damped"]
    assert failed["status"] == "failed"
    assert failed["failed_folds"] == 1
    assert failed["n_folds"] + 1 == failed["expected_folds"]
    assert failed["rmse"] is None
    assert failed["mape"] is None
    assert failed["horizon_metrics"] == {}


@pytest.mark.parametrize("failure", ["nan", "inf", "short", "wrong_dates"])
def test_invalid_predictions_are_reported_as_failed_folds(monkeypatch, failure) -> None:
    class InvalidForecaster(NaiveForecaster):
        def predict(self, horizon):
            forecast = super().predict(horizon)
            if failure == "short":
                return forecast.iloc[:-1]
            if failure == "wrong_dates":
                forecast.index = forecast.index + pd.offsets.MonthBegin(1)
            else:
                forecast.iloc[0] = float(failure)
            return forecast

    monkeypatch.setattr(forecast_pipeline, "FORECASTERS", {"invalid": InvalidForecaster})
    failed = evaluate_walk_forward(_make_series(n=14), horizon=3)["invalid"]

    assert failed["status"] == "failed"
    assert failed["failed_folds"] == failed["expected_folds"] == 6
    assert failed["n_folds"] == 0
    assert failed["rmse"] is None
    json.dumps(failed, allow_nan=False)


def test_validation_clips_negative_spending_and_handles_zero_actuals(monkeypatch) -> None:
    class NegativeForecaster(NaiveForecaster):
        def predict(self, horizon):
            return super().predict(horizon) - 100.0

    monkeypatch.setattr(forecast_pipeline, "FORECASTERS", {"negative": NegativeForecaster})
    series = pd.Series(0.0, index=pd.date_range("2023-01-01", periods=14, freq="MS"))
    metrics = evaluate_walk_forward(series, horizon=3)["negative"]

    assert metrics["status"] == "ok"
    assert metrics["rmse"] == 0.0
    assert metrics["mape"] is None
    assert all(item["rmse"] == 0.0 for item in metrics["horizon_metrics"].values())
    json.dumps(metrics, allow_nan=False)


def test_forecast_best_respects_explicit_minimum_validation_folds() -> None:
    series = _make_series(n=29)
    result = forecast_best(series, horizon=3, min_validation_folds=3)

    assert result.validation_metrics["seasonal_naive"]["status"] == "ok"
    assert result.validation_folds == 3


def test_category_history_extends_to_global_observation_end_without_leading_zeros() -> None:
    frame = pd.DataFrame({
        "booking_date": ["2024-01-01", "2024-03-01", "2024-05-01", "2024-09-01"],
        "amount": [-50.0, -100.0, -200.0, 5000.0],
        "direction": ["debit", "debit", "debit", "credit"],
        "category": ["transport", "food", "transport", None],
        "transaction_type": ["expense", "expense", "expense", "salary"],
    })

    series = build_monthly_series(frame, category="food", exclude_incomplete_month=True)

    assert series.index.tolist() == list(pd.date_range("2024-03-01", "2024-09-01", freq="MS"))
    assert series.tolist() == [100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert build_monthly_series(frame, category="health").empty


def test_category_padding_stops_before_incomplete_month(monkeypatch) -> None:
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 27)

    monkeypatch.setattr(forecast_pipeline, "date", FixedDate)
    frame = pd.DataFrame({
        "booking_date": ["2026-06-01", "2026-09-01", "2026-12-01"],
        "amount": [-100.0, 5000.0, -300.0],
        "direction": ["debit", "credit", "debit"],
        "category": ["food", None, "food"],
        "transaction_type": ["expense", "salary", "expense"],
    })

    series = build_monthly_series(frame, category="food", exclude_incomplete_month=True)

    assert series.index.tolist() == list(pd.date_range("2026-06-01", "2026-08-01", freq="MS"))
    assert series.tolist() == [100.0, 0.0, 0.0]
    without_current_month = build_monthly_series(
        frame.iloc[[0, 2]], category="food", exclude_incomplete_month=True,
    )
    assert without_current_month.index.tolist() == [pd.Timestamp("2026-06-01")]


def test_category_with_only_incomplete_history_is_empty(monkeypatch) -> None:
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 27)

    monkeypatch.setattr(forecast_pipeline, "date", FixedDate)
    frame = pd.DataFrame({
        "booking_date": ["2026-09-01"], "amount": [-100.0],
        "direction": ["debit"], "category": ["food"],
    })
    assert build_monthly_series(frame, category="food", exclude_incomplete_month=True).empty
    assert build_monthly_series(pd.DataFrame(), category="food").empty
