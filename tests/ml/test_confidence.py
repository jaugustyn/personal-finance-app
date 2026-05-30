"""Regression tests for shared classifier confidence helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from finance.ml.classification.confidence import (
    max_prediction_confidence,
    softmax_margin_confidence,
)


class _ProbaModel:
    def predict_proba(self, _x: pd.DataFrame) -> np.ndarray:
        return np.asarray([[0.2, 0.8]])


class _MarginModel:
    def predict(self, _x: pd.DataFrame) -> np.ndarray:
        return np.asarray(["food"])

    def decision_function(self, _x: pd.DataFrame) -> np.ndarray:
        return np.asarray([[0.0, 2.0, -1.0]])


class _BrokenModel:
    def predict_proba(self, _x: pd.DataFrame) -> np.ndarray:
        raise RuntimeError("not available")


def test_max_prediction_confidence_prefers_predict_proba() -> None:
    confidence = max_prediction_confidence(_ProbaModel(), pd.DataFrame([{"text": "x"}]))
    assert confidence == pytest.approx(0.8)


def test_max_prediction_confidence_uses_decision_margin_proxy() -> None:
    confidence = max_prediction_confidence(_MarginModel(), pd.DataFrame([{"text": "x"}]))
    assert confidence == pytest.approx(float(softmax_margin_confidence(np.asarray([[0.0, 2.0, -1.0]]))[0]))


def test_max_prediction_confidence_returns_none_on_estimator_error() -> None:
    assert max_prediction_confidence(_BrokenModel(), pd.DataFrame([{"text": "x"}])) is None


def test_softmax_margin_confidence_handles_binary_margins() -> None:
    confidence = softmax_margin_confidence(np.asarray([-2.0, 0.0, 2.0]))
    assert confidence.shape == (3,)
    assert confidence[1] == pytest.approx(0.5)
    assert confidence[0] == pytest.approx(confidence[2])
