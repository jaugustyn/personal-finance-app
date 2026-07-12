"""Leakage-resistant evaluation for promotable category classifier candidates."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score, log_loss
from sklearn.model_selection import (
    StratifiedGroupKFold,
    StratifiedKFold,
    cross_val_predict,
)

from finance.domain.enums import Category
from finance.ml.classification.evaluation_sets import thesis_data_readiness
from finance.ml.classification.pipeline import (
    build_pipeline,
    build_pipeline_v2,
    to_features,
    to_features_v2,
)
from finance.ml.classification.registry import ESTIMATORS
from finance.transactions.merchants import merchant_canonical_key

PROMOTABLE_ESTIMATORS = ("logreg", "linear_svc_calibrated")
PROMOTABLE_FEATURE_SETS = ("baseline", "feature_v2")
BENCHMARK_ONLY_ESTIMATORS = ("dummy_most_frequent", "linear_svc", "random_forest")
ALL_LABELS = sorted(item.value for item in Category)
TARGET_COVERED_ACCURACY = 0.90
TECHNICAL_MIN_TOTAL = 300
TECHNICAL_MIN_MACRO_F1 = 0.60
THESIS_MIN_MACRO_F1 = 0.75
THESIS_MIN_COVERAGE = 0.50
MAX_REGRESSION = 0.02
MAX_P99_MS = 200.0


@dataclass(frozen=True)
class CandidateEvaluation:
    estimator: str
    feature_set: str
    pipeline: Any
    metrics: dict[str, Any]
    confidence_policy: dict[str, Any]
    gates: dict[str, Any]


@dataclass(frozen=True)
class PreparedExperiment:
    """Validated split membership and its leakage-free training pool."""

    split_ids: dict[str, set[int]]
    training_pool: pd.DataFrame


def candidate_variants(
    estimator: str | None = None,
    feature_set: str | None = None,
) -> list[tuple[str, str]]:
    # Routine retraining deliberately stays cheap and understandable.  The
    # broader matrix remains available through the explicit benchmark mode.
    estimators = (estimator or "logreg",)
    feature_sets = (feature_set or "baseline",)
    invalid_estimators = set(estimators) - set(PROMOTABLE_ESTIMATORS)
    invalid_features = set(feature_sets) - set(PROMOTABLE_FEATURE_SETS)
    if invalid_estimators:
        raise ValueError(f"Estimator is benchmark-only: {sorted(invalid_estimators)}")
    if invalid_features:
        raise ValueError(f"Unknown feature set: {sorted(invalid_features)}")
    return [(name, features) for name in estimators for features in feature_sets]


def full_matrix_variants() -> list[tuple[str, str, bool]]:
    """Return the fixed thesis matrix and mark variants eligible for promotion."""
    return [
        *[
            (estimator, feature_set, True)
            for estimator in PROMOTABLE_ESTIMATORS
            for feature_set in PROMOTABLE_FEATURE_SETS
        ],
        *[
            (estimator, feature_set, False)
            for estimator in BENCHMARK_ONLY_ESTIMATORS
            for feature_set in PROMOTABLE_FEATURE_SETS
        ],
    ]


def _builders(feature_set: str):
    if feature_set == "baseline":
        return build_pipeline, to_features
    if feature_set == "feature_v2":
        return build_pipeline_v2, to_features_v2
    raise ValueError(f"Unknown feature set: {feature_set}")


def _merchant_groups(df: pd.DataFrame) -> pd.Series:
    return pd.Series(
        [
            merchant_canonical_key(str(merchant or ""), str(title or ""))
            or f"missing:{transaction_id}"
            for merchant, title, transaction_id in zip(
                df["merchant"], df["title"], df["transaction_id"], strict=False
            )
        ],
        index=df.index,
    )


def development_split_ids(df: pd.DataFrame) -> dict[str, set[int]]:
    """Create deterministic development slices; frozen sets replace these later."""
    ordered = df.sort_values(["booking_date", "transaction_id"], kind="stable")
    time_size = max(1, math.ceil(len(ordered) * 0.20))
    time_ids = set(ordered.tail(time_size)["transaction_id"].astype(int))

    groups = _merchant_groups(df)
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    placeholder = np.zeros(len(df))
    candidates: list[tuple[float, int, np.ndarray]] = []
    for fold_index, (_, test_idx) in enumerate(
        splitter.split(placeholder, df["category"].astype(str), groups)
    ):
        test_labels = set(df.iloc[test_idx]["category"].astype(str))
        train_labels = set(df.drop(df.index[test_idx])["category"].astype(str))
        if test_labels != set(ALL_LABELS) or train_labels != set(ALL_LABELS):
            continue
        distance = abs((len(test_idx) / len(df)) - 0.20)
        candidates.append((distance, fold_index, test_idx))
    if not candidates:
        raise ValueError(
            "Development merchant holdout cannot represent all nine classes in train and test."
        )
    _, _, selected = min(candidates, key=lambda item: (item[0], item[1]))
    merchant_ids = set(df.iloc[selected]["transaction_id"].astype(int))
    return {"time": time_ids, "merchant": merchant_ids}


def prepare_experiment(
    df: pd.DataFrame,
    *,
    split_ids: dict[str, set[int]] | None = None,
) -> PreparedExperiment:
    """Prepare deterministic splits once and validate the shared training pool."""
    resolved_splits = split_ids if split_ids is not None else development_split_ids(df)
    excluded = set().union(*resolved_splits.values())
    training_pool = df[
        ~df["transaction_id"].astype(int).isin(excluded)
    ].reset_index(drop=True)
    if training_pool.empty or training_pool["category"].nunique() != len(ALL_LABELS):
        raise ValueError("Training pool must contain all nine category classes.")
    counts = training_pool["category"].astype(str).value_counts()
    if any(int(counts.get(label, 0)) < 5 for label in ALL_LABELS):
        raise ValueError("Training pool needs at least five examples of every class.")
    return PreparedExperiment(
        split_ids=resolved_splits,
        training_pool=training_pool,
    )


def _derive_threshold(
    truth: np.ndarray,
    predicted: np.ndarray,
    confidence: np.ndarray,
    *,
    eligible: np.ndarray | None = None,
    min_covered: int,
) -> dict[str, float | int | None]:
    eligible_mask = eligible if eligible is not None else np.ones(len(truth), dtype=bool)
    best: dict[str, float | int | None] | None = None
    for threshold in sorted(set(float(value) for value in confidence)):
        covered_mask = eligible_mask & (confidence >= threshold)
        covered = int(covered_mask.sum())
        if covered < min_covered:
            continue
        accuracy = float((truth[covered_mask] == predicted[covered_mask]).mean())
        if accuracy < TARGET_COVERED_ACCURACY:
            continue
        coverage = float(covered / max(int(eligible_mask.sum()), 1))
        candidate: dict[str, float | int | None] = {
            "threshold": threshold,
            "covered": covered,
            "coverage": coverage,
            "accuracy_on_covered": accuracy,
        }
        if best is None or coverage > float(best["coverage"] or 0.0):
            best = candidate
    return best or {
        "threshold": 0.55,
        "covered": 0,
        "coverage": 0.0,
        "accuracy_on_covered": None,
    }


def derive_confidence_policy(
    truth: np.ndarray,
    predicted: np.ndarray,
    confidence: np.ndarray,
) -> dict[str, Any]:
    global_min = max(30, math.ceil(len(truth) * 0.10))
    global_point = _derive_threshold(
        truth,
        predicted,
        confidence,
        min_covered=global_min,
    )
    per_category: dict[str, dict[str, float | int | None]] = {}
    for label in ALL_LABELS:
        predicted_label = predicted == label
        if int(predicted_label.sum()) < 20:
            per_category[label] = {
                **global_point,
                "threshold": global_point["threshold"],
                "inherited_global": True,
            }
            continue
        point = _derive_threshold(
            truth,
            predicted,
            confidence,
            eligible=predicted_label,
            min_covered=10,
        )
        if int(point["covered"] or 0) < 10:
            point = {
                **global_point,
                "threshold": global_point["threshold"],
                "inherited_global": True,
            }
        else:
            point["inherited_global"] = False
        per_category[label] = point
    return {
        "source": "real_oof_predictions",
        "target_accuracy": TARGET_COVERED_ACCURACY,
        "default_threshold": global_point["threshold"],
        "global": global_point,
        "per_category": per_category,
        "allow_other_accept": False,
    }


def _policy_thresholds(policy: dict[str, Any], predicted: np.ndarray) -> np.ndarray:
    default = float(policy["default_threshold"])
    per_category = policy.get("per_category", {})
    return np.asarray(
        [
            float(per_category.get(str(label), {}).get("threshold", default))
            for label in predicted
        ]
    )


def _calibration_metrics(
    truth: np.ndarray,
    predicted: np.ndarray,
    proba: np.ndarray,
    classes: np.ndarray,
) -> dict[str, Any]:
    class_index = {str(label): index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(proba, dtype=float)
    for row_index, label in enumerate(truth):
        one_hot[row_index, class_index[str(label)]] = 1.0
    confidence = proba.max(axis=1)
    correct = (truth == predicted).astype(float)
    bins: list[dict[str, float | int]] = []
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
        bins.append(
            {
                "lower": float(lower),
                "upper": float(min(upper, 1.0)),
                "count": count,
                "accuracy": accuracy,
                "mean_confidence": mean_confidence,
            }
        )
    return {
        "log_loss": float(log_loss(truth, proba, labels=list(classes))),
        "brier_multiclass": float(np.mean(np.sum((proba - one_hot) ** 2, axis=1))),
        "ece": float(ece),
        "reliability_bins": bins,
    }


def _slice_metrics(
    pipeline: Any,
    frame: pd.DataFrame,
    feature_selector: Any,
    policy: dict[str, Any],
) -> dict[str, Any]:
    X = feature_selector(frame)  # noqa: N806
    truth = frame["category"].astype(str).to_numpy()
    predicted = np.asarray(pipeline.predict(X)).astype(str)
    proba = np.asarray(pipeline.predict_proba(X), dtype=float)
    confidence = proba.max(axis=1)
    thresholds = _policy_thresholds(policy, predicted)
    covered_mask = (confidence >= thresholds) & (predicted != Category.OTHER.value)
    covered = int(covered_mask.sum())
    report = classification_report(
        truth,
        predicted,
        labels=ALL_LABELS,
        output_dict=True,
        zero_division=0,
    )
    return {
        "n": int(len(frame)),
        "macro_f1": float(
            f1_score(
                truth, predicted, labels=ALL_LABELS, average="macro", zero_division=0
            )
        ),
        "weighted_f1": float(
            f1_score(
                truth,
                predicted,
                labels=ALL_LABELS,
                average="weighted",
                zero_division=0,
            )
        ),
        "per_category": report,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=ALL_LABELS).tolist(),
        "coverage": float(covered / len(frame)),
        "covered": covered,
        "accuracy_on_covered": (
            float((truth[covered_mask] == predicted[covered_mask]).mean())
            if covered
            else None
        ),
        "calibration": _calibration_metrics(
            truth, predicted, proba, np.asarray(pipeline.classes_)
        ),
    }


def _prediction_metrics(truth: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    report = classification_report(
        truth,
        predicted,
        labels=ALL_LABELS,
        output_dict=True,
        zero_division=0,
    )
    return {
        "n": int(len(truth)),
        "macro_f1": float(
            f1_score(
                truth,
                predicted,
                labels=ALL_LABELS,
                average="macro",
                zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(
                truth,
                predicted,
                labels=ALL_LABELS,
                average="weighted",
                zero_division=0,
            )
        ),
        "per_category": report,
        "confusion_matrix": confusion_matrix(
            truth,
            predicted,
            labels=ALL_LABELS,
        ).tolist(),
    }


def evaluate_pipeline_slices(
    df: pd.DataFrame,
    *,
    pipeline: Any,
    feature_set: str,
    split_ids: dict[str, set[int]],
    confidence_policy: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate an already fitted pipeline on the exact candidate holdouts."""
    _, feature_selector = _builders(feature_set)
    slices: dict[str, Any] = {}
    for split in ("time", "merchant"):
        ids = split_ids.get(split, set())
        frame = df[df["transaction_id"].astype(int).isin(ids)].reset_index(drop=True)
        if frame.empty:
            raise ValueError(f"Empty {split} holdout.")
        slices[split] = _slice_metrics(
            pipeline,
            frame,
            feature_selector,
            confidence_policy,
        )
    return slices


def _latency_p99_ms(pipeline: Any, sample: pd.DataFrame, feature_selector: Any) -> float:
    X = feature_selector(sample.iloc[[0]])  # noqa: N806
    for _ in range(10):
        pipeline.predict(X)
        pipeline.predict_proba(X)
    samples = []
    for _ in range(1000):
        started = time.perf_counter_ns()
        pipeline.predict(X)
        pipeline.predict_proba(X)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return float(np.percentile(samples, 99))


def _prediction_latency_p99_ms(
    pipeline: Any,
    sample: pd.DataFrame,
    feature_selector: Any,
) -> float:
    X = feature_selector(sample.iloc[[0]])  # noqa: N806
    for _ in range(10):
        pipeline.predict(X)
    samples = []
    for _ in range(1000):
        started = time.perf_counter_ns()
        pipeline.predict(X)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return float(np.percentile(samples, 99))


def evaluate_benchmark(
    df: pd.DataFrame,
    *,
    estimator: str,
    feature_set: str,
    split_ids: dict[str, set[int]],
) -> dict[str, Any]:
    """Evaluate a research-only model without creating a promotable artifact."""
    if estimator not in BENCHMARK_ONLY_ESTIMATORS:
        raise ValueError(f"Not a benchmark-only estimator: {estimator}")
    pipeline_builder, feature_selector = _builders(feature_set)
    train = prepare_experiment(df, split_ids=split_ids).training_pool
    y_train = train["category"].astype(str)
    X_train = feature_selector(train)  # noqa: N806
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof_pipeline = pipeline_builder(ESTIMATORS[estimator]())
    oof_predicted = np.asarray(
        cross_val_predict(oof_pipeline, X_train, y_train, cv=cv, method="predict")
    ).astype(str)
    pipeline = pipeline_builder(ESTIMATORS[estimator]())
    pipeline.fit(X_train, y_train)
    slices: dict[str, Any] = {}
    for split in ("time", "merchant"):
        frame = df[
            df["transaction_id"].astype(int).isin(split_ids.get(split, set()))
        ].reset_index(drop=True)
        if frame.empty:
            raise ValueError(f"Empty {split} holdout.")
        truth = frame["category"].astype(str).to_numpy()
        predicted = np.asarray(pipeline.predict(feature_selector(frame))).astype(str)
        slices[split] = _prediction_metrics(truth, predicted)
    return {
        "estimator": estimator,
        "feature_set": feature_set,
        "benchmark_only": True,
        "promotable": False,
        "stratified_cv": _prediction_metrics(y_train.to_numpy(), oof_predicted),
        "time": slices["time"],
        "merchant": slices["merchant"],
        "p99_ms": _prediction_latency_p99_ms(pipeline, train, feature_selector),
    }


def evaluate_candidate(
    df: pd.DataFrame,
    *,
    estimator: str,
    feature_set: str,
    split_ids: dict[str, set[int]],
    frozen_evaluation_set: bool,
    active_metrics: dict[str, Any] | None = None,
) -> CandidateEvaluation:
    pipeline_builder, feature_selector = _builders(feature_set)
    train = prepare_experiment(df, split_ids=split_ids).training_pool
    y_train = train["category"].astype(str)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    X_train = feature_selector(train)  # noqa: N806
    oof_pipeline = pipeline_builder(ESTIMATORS[estimator]())
    oof_proba = np.asarray(
        cross_val_predict(oof_pipeline, X_train, y_train, cv=cv, method="predict_proba"),
        dtype=float,
    )
    oof_classes = np.asarray(sorted(y_train.unique())).astype(str)
    oof_predicted = oof_classes[np.argmax(oof_proba, axis=1)]
    confidence_policy = derive_confidence_policy(
        y_train.to_numpy(), oof_predicted, oof_proba.max(axis=1)
    )

    pipeline = pipeline_builder(ESTIMATORS[estimator]())
    pipeline.fit(X_train, y_train)
    slices = evaluate_pipeline_slices(
        df,
        pipeline=pipeline,
        feature_set=feature_set,
        split_ids=split_ids,
        confidence_policy=confidence_policy,
    )

    p99_ms = _latency_p99_ms(pipeline, train, feature_selector)
    technical_checks = {
        "total_at_least_300": len(df) >= TECHNICAL_MIN_TOTAL,
        "time_macro_f1_at_least_060": slices["time"]["macro_f1"] >= TECHNICAL_MIN_MACRO_F1,
        "merchant_macro_f1_at_least_060": slices["merchant"]["macro_f1"] >= TECHNICAL_MIN_MACRO_F1,
        "p99_at_most_200_ms": p99_ms <= MAX_P99_MS,
    }
    regression = None
    if active_metrics:
        regression = max(
            float(active_metrics.get("time", {}).get("macro_f1", 0.0))
            - float(slices["time"]["macro_f1"]),
            float(active_metrics.get("merchant", {}).get("macro_f1", 0.0))
            - float(slices["merchant"]["macro_f1"]),
        )
        technical_checks["regression_at_most_002"] = regression <= MAX_REGRESSION
    technical_passed = all(technical_checks.values())

    thesis_readiness = thesis_data_readiness(df)
    thesis_checks = {
        "frozen_evaluation_set": frozen_evaluation_set,
        "thesis_data_ready": bool(thesis_readiness["ready"]),
        "time_macro_f1_at_least_075": slices["time"]["macro_f1"] >= THESIS_MIN_MACRO_F1,
        "merchant_macro_f1_at_least_075": slices["merchant"]["macro_f1"] >= THESIS_MIN_MACRO_F1,
        "time_coverage_at_least_050": slices["time"]["coverage"] >= THESIS_MIN_COVERAGE,
        "merchant_coverage_at_least_050": slices["merchant"]["coverage"] >= THESIS_MIN_COVERAGE,
        "time_covered_accuracy_at_least_090": (
            slices["time"]["accuracy_on_covered"] is not None
            and slices["time"]["accuracy_on_covered"] >= TARGET_COVERED_ACCURACY
        ),
        "merchant_covered_accuracy_at_least_090": (
            slices["merchant"]["accuracy_on_covered"] is not None
            and slices["merchant"]["accuracy_on_covered"] >= TARGET_COVERED_ACCURACY
        ),
        "technical_gate": technical_passed,
    }
    thesis_passed = all(thesis_checks.values())
    covered_accuracies = [
        value
        for value in (
            slices["time"]["accuracy_on_covered"],
            slices["merchant"]["accuracy_on_covered"],
        )
        if value is not None
    ]
    metrics = {
        "time": slices["time"],
        "merchant": slices["merchant"],
        "oof": {
            "n": len(train),
            **_prediction_metrics(y_train.to_numpy(), oof_predicted),
            "calibration": _calibration_metrics(
                y_train.to_numpy(),
                oof_predicted,
                oof_proba,
                oof_classes,
            ),
        },
        "p99_ms": p99_ms,
        "ranking": {
            "worst_macro_f1": min(
                slices["time"]["macro_f1"], slices["merchant"]["macro_f1"]
            ),
            "mean_macro_f1": (
                slices["time"]["macro_f1"] + slices["merchant"]["macro_f1"]
            )
            / 2,
            "mean_covered_accuracy": (
                float(np.mean(covered_accuracies)) if covered_accuracies else 0.0
            ),
        },
    }
    return CandidateEvaluation(
        estimator=estimator,
        feature_set=feature_set,
        pipeline=pipeline,
        metrics=metrics,
        confidence_policy=confidence_policy,
        gates={
            "technical": {"passed": technical_passed, "checks": technical_checks},
            "thesis": {"passed": thesis_passed, "checks": thesis_checks},
            "regression": regression,
            "promotable": technical_passed,
            "level": (
                "thesis_ready"
                if thesis_passed
                else "technical"
                if technical_passed
                else "rejected"
            ),
        },
    )


def rank_evaluations(evaluations: list[CandidateEvaluation]) -> list[CandidateEvaluation]:
    return sorted(
        evaluations,
        key=lambda result: (
            -float(result.metrics["ranking"]["worst_macro_f1"]),
            -float(result.metrics["ranking"]["mean_macro_f1"]),
            -float(result.metrics["ranking"]["mean_covered_accuracy"]),
            float(result.metrics["p99_ms"]),
        ),
    )
