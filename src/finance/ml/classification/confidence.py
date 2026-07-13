"""Shared confidence helpers for classifier runtime and evidence reports."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _prediction_confidence_vector(
    model: Any,
    X: pd.DataFrame,  # noqa: N803
) -> tuple[list[str], np.ndarray] | None:
    """Return class labels and one-row confidence vector for top-k diagnostics."""
    try:
        named_steps = getattr(model, "named_steps", {})
        clf = named_steps.get("clf", model) if isinstance(named_steps, dict) else model
        raw_classes = getattr(clf, "classes_", None)
        if raw_classes is None:
            return None
        classes = [str(item) for item in raw_classes]
        if not hasattr(model, "predict_proba"):
            return None
        proba = np.asarray(model.predict_proba(X), dtype=float)
        if proba.ndim == 1:
            proba = proba.reshape(1, -1)
        if proba.shape[0] != 1:
            return None
        return classes, proba[0]
    except Exception:
        return None
    return None


def predict_with_probabilities(
    model: Any,
    X: pd.DataFrame,  # noqa: N803
    *,
    k: int = 3,
) -> tuple[str, float, list[dict[str, float | str]]] | None:
    """Predict once and derive category, confidence and top-k from one vector."""
    vector = _prediction_confidence_vector(model, X)
    if vector is None:
        return None
    classes, confidences = vector
    if not classes or len(classes) != len(confidences):
        return None
    best_index = int(np.argmax(confidences))
    pairs = sorted(
        zip(classes, confidences, strict=True),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    top_predictions: list[dict[str, float | str]] = [
        {"category": category, "confidence": float(confidence)}
        for category, confidence in pairs[: max(k, 1)]
    ]
    return (
        classes[best_index],
        float(confidences[best_index]),
        top_predictions,
    )
