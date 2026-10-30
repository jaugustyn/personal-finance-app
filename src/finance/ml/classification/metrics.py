"""Typed aggregate classification metrics shared by candidates and experiments."""
from __future__ import annotations

from typing import TypedDict

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score, log_loss


class PredictionMetrics(TypedDict):
    n: int
    macro_f1: float
    weighted_f1: float
    per_category: dict[str, dict[str, float] | float]
    confusion_matrix: list[list[int]]


class ReliabilityBin(TypedDict):
    lower: float
    upper: float
    count: int
    accuracy: float
    mean_confidence: float


class CalibrationMetrics(TypedDict):
    log_loss: float
    brier_multiclass: float
    ece: float
    reliability_bins: list[ReliabilityBin]


class CalibratedPredictionMetrics(PredictionMetrics):
    calibration: CalibrationMetrics


class HoldoutMetrics(CalibratedPredictionMetrics):
    coverage: float
    covered: int
    accuracy_on_covered: float | None


def prediction_metrics(
    truth: np.ndarray,
    predicted: np.ndarray,
    *,
    labels: list[str],
) -> PredictionMetrics:
    return {
        "n": int(len(truth)),
        "macro_f1": float(
            f1_score(truth, predicted, labels=labels, average="macro", zero_division=0)
        ),
        "weighted_f1": float(
            f1_score(truth, predicted, labels=labels, average="weighted", zero_division=0)
        ),
        "per_category": classification_report(
            truth, predicted, labels=labels, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(truth, predicted, labels=labels).tolist(),
    }


def calibration_metrics(
    truth: np.ndarray,
    predicted: np.ndarray,
    proba: np.ndarray,
    classes: np.ndarray,
) -> CalibrationMetrics:
    class_index = {str(label): index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(proba, dtype=float)
    for row_index, label in enumerate(truth):
        one_hot[row_index, class_index[str(label)]] = 1.0
    confidence = proba.max(axis=1)
    correct = (truth == predicted).astype(float)
    bins: list[ReliabilityBin] = []
    ece = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        mask = (confidence >= lower) & (
            confidence <= upper if upper >= 1.0 else confidence < upper
        )
        count = int(mask.sum())
        if not count:
            continue
        accuracy = float(correct[mask].mean())
        mean_confidence = float(confidence[mask].mean())
        ece += (count / len(truth)) * abs(accuracy - mean_confidence)
        bins.append({
            "lower": float(lower),
            "upper": float(min(upper, 1.0)),
            "count": count,
            "accuracy": accuracy,
            "mean_confidence": mean_confidence,
        })
    return {
        "log_loss": float(log_loss(truth, proba, labels=list(classes))),
        "brier_multiclass": float(np.mean(np.sum((proba - one_hot) ** 2, axis=1))),
        "ece": float(ece),
        "reliability_bins": bins,
    }
