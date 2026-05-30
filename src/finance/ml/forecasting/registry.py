"""Forecaster registry: small, interchangeable wrappers.

Constraint: dataset is short (≈9 months) → ARIMA/Prophet can be brittle.
We start with cheap, robust baselines (Naive last-month, monthly mean,
exponential smoothing). ARIMA wrapper is provided but only kicks in when
we have ≥12 monthly observations.
"""
from __future__ import annotations

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
        if self.alpha is not None:
            self._fitted = model.fit(smoothing_level=self.alpha, optimized=False)
        else:
            self._fitted = model.fit(optimized=True)
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._fitted is None:
            raise RuntimeError("SESForecaster not fitted")
        fc = self._fitted.forecast(horizon)
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series(np.asarray(fc, dtype=float), index=idx, name=self.name)


class ARIMAForecaster:
    """Tiny ARIMA(p,d,q) wrapper. Only safe with ≥12 observations."""
    name = "arima"

    def __init__(self, order: tuple[int, int, int] = (1, 1, 1)) -> None:
        self.order = order
        self._fitted = None
        self._last_index: pd.Timestamp | None = None

    def fit(self, y: pd.Series) -> ARIMAForecaster:
        from statsmodels.tsa.arima.model import ARIMA

        if len(y) < 8:
            raise ValueError("ARIMA needs at least 8 observations")
        self._fitted = ARIMA(y.astype(float), order=self.order).fit()
        self._last_index = y.index[-1]
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._fitted is None:
            raise RuntimeError("ARIMAForecaster not fitted")
        fc = self._fitted.forecast(steps=horizon)
        idx = pd.date_range(
            start=self._last_index + pd.offsets.MonthBegin(1),
            periods=horizon,
            freq="MS",
        )
        return pd.Series(np.asarray(fc, dtype=float), index=idx, name=self.name)


FORECASTERS: dict[str, type] = {
    "naive": NaiveForecaster,
    "mean3": MeanForecaster,
    "ses": SESForecaster,
    "arima": ARIMAForecaster,
}
