"""Forecaster registry: small, interchangeable wrappers.

The registry deliberately stays small: robust flat baselines, one damped trend
model and a seasonal baseline that is enabled only for sufficiently long data.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd


class Forecaster(Protocol):
    name: str

    def fit(self, y: pd.Series) -> Forecaster: ...
    def predict(self, horizon: int) -> pd.Series: ...


@dataclass
class NaiveForecaster:
    """Predict the last observed value for every future step."""
    name: str = "naive"
    _last: float = 0.0
    _last_index: pd.Timestamp | None = None

    def fit(self, y: pd.Series) -> NaiveForecaster:
        if len(y) == 0:
            raise ValueError("Empty series")
        self._last = float(y.iloc[-1])
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series([self._last] * horizon, index=idx, name=self.name)


@dataclass
class MeanForecaster:
    """Predict the rolling-3 mean of the most recent observations."""
    name: str = "mean3"
    window: int = 3
    _mean: float = 0.0
    _last_index: pd.Timestamp | None = None

    def fit(self, y: pd.Series) -> MeanForecaster:
        if len(y) == 0:
            raise ValueError("Empty series")
        tail = y.tail(self.window)
        self._mean = float(tail.mean())
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series([self._mean] * horizon, index=idx, name=self.name)


class SESForecaster:
    """Simple Exponential Smoothing (statsmodels)."""
    name = "ses"

    def __init__(self, alpha: float | None = None) -> None:
        self.alpha = alpha
        self._fitted = None
        self._last_index: pd.Timestamp | None = None

    def fit(self, y: pd.Series) -> SESForecaster:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing

        if len(y) < 2:
            raise ValueError("SES requires at least 2 points")
        model = SimpleExpSmoothing(y.astype(float), initialization_method="estimated")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            if self.alpha is not None:
                self._fitted = model.fit(smoothing_level=self.alpha, optimized=False)
            else:
                self._fitted = model.fit(optimized=True)
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._fitted is None:
            raise RuntimeError("SESForecaster not fitted")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            fc = self._fitted.forecast(horizon)
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series(np.asarray(fc, dtype=float), index=idx, name=self.name)


class HoltDampedForecaster:
    """Holt trend with damping to avoid unrealistic long-range growth."""

    name = "holt_damped"

    def __init__(self) -> None:
        self._fitted = None
        self._last_index: pd.Timestamp | None = None

    def fit(self, y: pd.Series) -> HoltDampedForecaster:
        from statsmodels.tsa.holtwinters import Holt

        if len(y) < 6:
            raise ValueError("Holt trend requires at least 6 observations")
        model = Holt(
            y.astype(float),
            damped_trend=True,
            initialization_method="estimated",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            self._fitted = model.fit(optimized=True)
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._fitted is None:
            raise RuntimeError("HoltDampedForecaster not fitted")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            fc = self._fitted.forecast(horizon)
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series(np.asarray(fc, dtype=float), index=idx, name=self.name)


@dataclass
class SeasonalNaiveForecaster:
    """Repeat the values observed in the same months of the previous year."""

    name: str = "seasonal_naive"
    season_length: int = 12
    _season: np.ndarray | None = None
    _last_index: pd.Timestamp | None = None

    def fit(self, y: pd.Series) -> SeasonalNaiveForecaster:
        if len(y) < self.season_length * 2:
            raise ValueError("Seasonal naive requires at least 24 observations")
        self._season = y.tail(self.season_length).to_numpy(dtype=float)
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._season is None or self._last_index is None:
            raise RuntimeError("SeasonalNaiveForecaster not fitted")
        values = [
            float(self._season[index % self.season_length])
            for index in range(horizon)
        ]
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series(values, index=idx, name=self.name)


FORECASTERS: dict[str, type] = {
    "naive": NaiveForecaster,
    "mean3": MeanForecaster,
    "ses": SESForecaster,
    "holt_damped": HoltDampedForecaster,
    "seasonal_naive": SeasonalNaiveForecaster,
}
