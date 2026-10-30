"""Offline feature comparison on identical confirmed data and validation splits."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, TypedDict

import pandas as pd

from finance.ml.classification.artifacts import runtime_versions
from finance.ml.classification.candidate_evaluation import (
    PROMOTABLE_ESTIMATORS,
    RESEARCH_FEATURE_SETS,
    CandidateMetrics,
    evaluate_candidate,
    prepare_experiment,
)
from finance.ml.classification.constants import DEFAULT_ACCEPT_THRESHOLD
from finance.ml.classification.evaluation import filter_category_training_rows
from finance.ml.classification.evaluation_sets import dataset_fingerprint


class FeatureVariant(TypedDict):
    estimator: str
    feature_set: str
    metrics: CandidateMetrics


class FeatureDelta(TypedDict):
    macro_f1: float
    weighted_f1: float
    coverage: float
    accuracy_on_covered: float | None


class FeatureComparisonReport(TypedDict):
    report_type: str
    schema_version: str
    created_at: str
    evaluation_role: str
    data_source: str
    evaluation_set_id: str | None
    dataset_fingerprint: str
    training_fingerprint: str
    split_fingerprints: dict[str, str]
    input_rows: int
    confirmed_rows: int
    excluded_unconfirmed_rows: int
    training_rows: int
    split_counts: dict[str, int]
    runtime_versions: dict[str, str]
    protocol: dict[str, object]
    variants: list[FeatureVariant]
    feature_v2_minus_baseline: dict[str, dict[str, FeatureDelta]]
    privacy_note: str


def compare_features(
    df: pd.DataFrame,
    *,
    split_ids: dict[str, set[int]],
    data_source: Literal["synthetic", "confirmed_local"],
    evaluation_set_id: str | None = None,
) -> FeatureComparisonReport:
    """Compare both calibrated classifiers without saving or activating models.

    Splits are supplied by the caller, never chosen based on variant scores.
    Filtering cannot silently replace a missing or unconfirmed holdout member:
    prepare_experiment rejects such a split before any training starts.
    """
    confirmed = filter_category_training_rows(df)
    if not confirmed.empty:
        # Accepted suggestions need the reference identifying their origin.
        origin = confirmed.get("category_origin_ref", pd.Series("", index=confirmed.index))
        confirmed = confirmed[
            (confirmed["category_confirmation_method"] == "manual")
            | origin.fillna("").astype(str).str.strip().ne("")
        ]
    if confirmed.empty:
        raise ValueError("No confirmed labels with complete provenance are available.")
    if not confirmed["transaction_id"].is_unique:
        raise ValueError("Transaction IDs must be unique within an experiment.")
    # SQL result order must not determine OOF fold membership.
    confirmed = confirmed.sort_values("transaction_id", kind="stable").reset_index(drop=True)
    prepared = prepare_experiment(confirmed, split_ids=split_ids)
    variants: list[FeatureVariant] = []
    deltas: dict[str, dict[str, FeatureDelta]] = {}
    for estimator in PROMOTABLE_ESTIMATORS:
        results: dict[str, CandidateMetrics] = {}
        for feature_set in RESEARCH_FEATURE_SETS:
            result = evaluate_candidate(
                confirmed,
                estimator=estimator,
                feature_set=feature_set,
                split_ids=prepared.split_ids,
                frozen_evaluation_set=evaluation_set_id is not None,
            )
            results[feature_set] = result.metrics
            variants.append({
                "estimator": estimator,
                "feature_set": feature_set,
                "metrics": result.metrics,
            })
        baseline, extended = results["baseline"], results["feature_v2"]
        deltas[estimator] = {}
        for name, base_slice, extended_slice in (
            ("time", baseline["time"], extended["time"]),
            ("merchant", baseline["merchant"], extended["merchant"]),
        ):
            base_accuracy = base_slice["accuracy_on_covered"]
            extended_accuracy = extended_slice["accuracy_on_covered"]
            deltas[estimator][name] = {
                "macro_f1": extended_slice["macro_f1"] - base_slice["macro_f1"],
                "weighted_f1": extended_slice["weighted_f1"] - base_slice["weighted_f1"],
                "coverage": extended_slice["coverage"] - base_slice["coverage"],
                "accuracy_on_covered": (
                    extended_accuracy - base_accuracy
                    if extended_accuracy is not None and base_accuracy is not None
                    else None
                ),
            }
    return {
        "report_type": "classification_feature_comparison",
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "evaluation_role": "development_validation",
        "data_source": data_source,
        "evaluation_set_id": evaluation_set_id,
        "dataset_fingerprint": dataset_fingerprint(confirmed),
        "training_fingerprint": dataset_fingerprint(prepared.training_pool),
        "split_fingerprints": {
            name: dataset_fingerprint(confirmed[confirmed["transaction_id"].isin(ids)])
            for name, ids in prepared.split_ids.items()
        },
        "input_rows": len(df),
        "confirmed_rows": len(confirmed),
        "excluded_unconfirmed_rows": len(df) - len(confirmed),
        "training_rows": len(prepared.training_pool),
        "split_counts": {name: len(ids) for name, ids in prepared.split_ids.items()},
        "runtime_versions": runtime_versions(),
        "protocol": {
            "oof": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
            "svc_random_state": 42,
            "confidence_threshold": DEFAULT_ACCEPT_THRESHOLD,
            "allow_other_accept": False,
            "training_order": "transaction_id ascending",
            "fit_scope": "before time cutoff, excluding all holdout merchant groups",
            "selection_rule": "compare macro-F1 separately on time and merchant validation",
            "final_test_evaluated": False,
        },
        "variants": variants,
        "feature_v2_minus_baseline": deltas,
        "privacy_note": "Aggregate metrics and fingerprints only; no raw transactions or models.",
    }
