"""Shared confidence helpers for classifier runtime and evidence reports."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_predict


def softmax_margin_confidence(scores: np.ndarray) -> np.ndarray:
    """Return a stable max-class confidence proxy from estimator margins."""
    arr = np.asarray(scores, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim == 1:
        arr = np.column_stack([-arr, arr])
    arr = arr - arr.max(axis=1, keepdims=True)
    exp = np.exp(arr)
    proba = exp / exp.sum(axis=1, keepdims=True)
    return proba.max(axis=1)


def max_prediction_confidence(model: Any, X: pd.DataFrame) -> float | None:  # noqa: N803
    """Best-effort confidence for one-row prediction payloads."""
    try:
        if hasattr(model, "predict_proba"):
            proba = np.asarray(model.predict_proba(X), dtype=float)
            if proba.ndim == 1:
                proba = proba.reshape(1, -1)
            return float(proba.max(axis=1)[0])
        if hasattr(model, "decision_function"):
            scores = np.asarray(model.decision_function(X), dtype=float)
            return float(softmax_margin_confidence(scores)[0])
    except Exception:
        return None
    return None


def prediction_confidence_vector(
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
        if hasattr(model, "predict_proba"):
            proba = np.asarray(model.predict_proba(X), dtype=float)
            if proba.ndim == 1:
                proba = proba.reshape(1, -1)
            return classes, proba[0]
        if hasattr(model, "decision_function"):
            scores = np.asarray(model.decision_function(X), dtype=float)
            if scores.ndim == 1:
                scores = np.column_stack([-scores, scores])
            scores = scores - scores.max(axis=1, keepdims=True)
            exp = np.exp(scores)
            proba = exp / exp.sum(axis=1, keepdims=True)
            return classes, proba[0]
    except Exception:
        return None
    return None


def top_prediction_confidences(
    model: Any,
    X: pd.DataFrame,  # noqa: N803
    *,
    k: int = 3,
) -> list[dict[str, float | str]]:
    vector = prediction_confidence_vector(model, X)
    if vector is None:
        return []
    classes, confidences = vector
    pairs = sorted(
        zip(classes, confidences, strict=False),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    return [
        {"category": category, "confidence": float(confidence)}
        for category, confidence in pairs[: max(k, 1)]
    ]


def cross_val_prediction_confidence(
    model: Any,
    X: pd.DataFrame,  # noqa: N803
    y: pd.Series,
    cv: Any,
) -> np.ndarray | None:
    """Best-effort out-of-fold confidence for threshold calibration."""
    try:
        if hasattr(model, "predict_proba"):
            proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba", n_jobs=None)
            proba_arr = np.asarray(proba, dtype=float)
            if proba_arr.ndim == 1:
                proba_arr = proba_arr.reshape(1, -1)
            return proba_arr.max(axis=1)
        if hasattr(model, "decision_function"):
            scores = cross_val_predict(
                model,
                X,
                y,
                cv=cv,
                method="decision_function",
                n_jobs=None,
            )
            return softmax_margin_confidence(np.asarray(scores, dtype=float))
    except Exception:
        return None
    return None
