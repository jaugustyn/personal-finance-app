"""Regression tests for shared classifier confidence helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from finance.ml.classification.confidence import predict_with_probabilities


class _ProbaModel:
    classes_ = np.asarray(["food", "transport"])

    def __init__(self) -> None:
        self.calls = 0

    def predict_proba(self, _x: pd.DataFrame) -> np.ndarray:
        self.calls += 1
        return np.asarray([[0.2, 0.8]])


class _BrokenModel:
    classes_ = np.asarray(["food", "transport"])

    def predict_proba(self, _x: pd.DataFrame) -> np.ndarray:
        raise RuntimeError("not available")


def test_probability_prediction_uses_one_model_call_for_all_diagnostics() -> None:
    model = _ProbaModel()

    result = predict_with_probabilities(model, pd.DataFrame([{"text": "x"}]))

    assert result == (
        "transport",
        pytest.approx(0.8),
        [
            {"category": "transport", "confidence": pytest.approx(0.8)},
            {"category": "food", "confidence": pytest.approx(0.2)},
        ],
    )
    assert model.calls == 1


def test_probability_prediction_returns_none_on_estimator_error() -> None:
    assert predict_with_probabilities(_BrokenModel(), pd.DataFrame([{"text": "x"}])) is None
