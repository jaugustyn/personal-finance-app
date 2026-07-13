"""Offline evidence assembled with the same evaluator as registered training jobs."""
from __future__ import annotations

from typing import Any

import pandas as pd

from finance.ml.classification.candidate_evaluation import (
    ValidationSplitNotFeasible,
    candidate_variants,
    development_split_ids,
    evaluate_candidate,
    rank_evaluations,
    supported_classification_rows,
)
from finance.ml.classification.constants import (
    DEFAULT_ACCEPT_THRESHOLD,
    MINIMUM_LABELLED_ROWS,
)
from finance.ml.classification.evaluation import (
    build_label_readiness,
    filter_category_training_rows,
)


def _mean(values: list[object]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, int | float)]
    return sum(numeric) / len(numeric) if numeric else None


def _model_report(result: Any) -> dict[str, Any]:
    metrics = result.metrics
    time_metrics = metrics["time"]
    merchant_metrics = metrics["merchant"]
    return {
        "macro_f1": metrics["ranking"]["mean_macro_f1"],
        "weighted_f1": _mean(
            [time_metrics.get("weighted_f1"), merchant_metrics.get("weighted_f1")]
        ),
        "confusion_matrix": time_metrics.get("confusion_matrix", []),
        "labels": metrics.get("labels", []),
        "time": time_metrics,
        "merchant": merchant_metrics,
        "oof": metrics.get("oof", {}),
        "p99_ms": metrics.get("p99_ms"),
        "gates": result.gates,
        "runtime_confidence_policy": result.confidence_policy,
        "oof_confidence_diagnostics": result.confidence_diagnostics,
    }


def build_evidence_report(
    real_df: pd.DataFrame,
    *,
    augmented_df: pd.DataFrame | None = None,
    external_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Evaluate the two baseline runtime candidates on confirmed real labels only."""
    confirmed = filter_category_training_rows(real_df)
    readiness = build_label_readiness(real_df)
    raw_category_counts = readiness.get("category_counts")
    category_counts = (
        dict(raw_category_counts) if isinstance(raw_category_counts, dict) else {}
    )
    separate_experiments = {
        "synthetic_rows": int(len(augmented_df)) if augmented_df is not None else 0,
        "external_rows": int(len(external_df)) if external_df is not None else 0,
        "note": (
            "Synthetic and external rows are reported separately and are not used "
            "for runtime candidate fitting or validation."
        ),
    }
    base: dict[str, Any] = {
        "report_type": "classification_evidence",
        "methodology": "shared_candidate_evaluation_v2",
        "selected_experiment": "confirmed_real_labels",
        "models": {},
        "class_counts": category_counts,
        "n_total_labelled": int(len(confirmed)),
        "n_classes": 0,
        "labels": [],
        "unsupported_classes": category_counts,
        "confidence_policy": {
            "source": "fixed_runtime_threshold",
            "default_threshold": DEFAULT_ACCEPT_THRESHOLD,
            "per_category": {},
            "allow_other_accept": False,
        },
        "label_readiness": readiness,
        "separate_experiments": separate_experiments,
        "privacy_note": "The report contains aggregate metrics only.",
    }
    if len(confirmed) < MINIMUM_LABELLED_ROWS:
        return base | {
            "skipped": True,
            "reason": "total_confirmed_labels_below_300",
            "diagnostics": {
                "required": MINIMUM_LABELLED_ROWS,
                "observed": int(len(confirmed)),
            },
        }

    try:
        _, labels, class_counts, unsupported = supported_classification_rows(confirmed)
        split_ids = development_split_ids(confirmed)
    except ValidationSplitNotFeasible as exc:
        return base | {
            "skipped": True,
            "reason": "validation_split_not_feasible",
            "diagnostics": {"error": str(exc), "class_counts": category_counts},
        }

    evaluations = [
        evaluate_candidate(
            confirmed,
            estimator=estimator,
            feature_set=feature_set,
            split_ids=split_ids,
            frozen_evaluation_set=False,
        )
        for estimator, feature_set in candidate_variants()
    ]
    ranked = rank_evaluations(evaluations)
    models = {result.estimator: _model_report(result) for result in ranked}
    recommended = next((result for result in ranked if result.gates["promotable"]), None)
    return base | {
        "skipped": False,
        "models": models,
        "class_counts": class_counts,
        "n_classes": len(labels),
        "labels": labels,
        "unsupported_classes": unsupported,
        "split_counts": {name: len(ids) for name, ids in split_ids.items()},
        "recommended_estimator": recommended.estimator if recommended else None,
        "validation_slices": {
            result.estimator: {
                "time": result.metrics["time"],
                "merchant": result.metrics["merchant"],
            }
            for result in ranked
        },
    }
