"""Train + evaluate transaction classifiers.

Two modes:
  - `--from-files PATH ...`  parse CSVs directly (no DB required)
  - `--from-db`              load labelled rows from PostgreSQL

Outputs a JSON report and (for the chosen `--persist` estimator) a joblib
artifact under `data/models/`.

Usage examples:

    python -m finance.ml.classification.train \\
        --from-files data/pekao_sa/*.csv \\
        --pekao
    python -m finance.ml.classification.train --from-db --persist linear_svc
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit, StratifiedKFold, cross_val_predict

from finance.analytics.filters import expense_category_candidate_mask
from finance.domain.enums import BankSource, Category
from finance.ingestion import get_parser
from finance.ml.classification.confidence import (
    cross_val_prediction_confidence,
    prediction_confidence_vector,
)
from finance.ml.classification.dataset import dtos_to_dataframe, load_training_set
from finance.ml.classification.external import load_kaggle_personal_finance
from finance.ml.classification.pipeline import (
    build_pipeline,
    build_pipeline_v2,
    to_features,
    to_features_v2,
)
from finance.ml.classification.registry import ESTIMATORS
from finance.transactions.normalization import normalize_merchant

MODELS_DIR = Path("data/models")
REPORTS_DIR = Path("data/reports")
MIN_PER_CLASS = 2  # minimum labelled samples per class to keep it for CV
CONFIDENCE_THRESHOLDS = [0.0, 0.5, 0.55, 0.6, 0.7, 0.8, 0.9]
EVIDENCE_THRESHOLD = 0.55
TARGET_THRESHOLD_ACCURACY = 0.9
FEATURE_SETS = {"baseline", "feature_v2"}
DEFAULT_FEATURE_SET = "baseline"
MINIMUM_LABELLED_ROWS = 300
RECOMMENDED_LABELLED_ROWS = 800
IDEAL_LABELLED_ROWS = 2000
MINIMUM_PER_CATEGORY = 20
RECOMMENDED_PER_CATEGORY = 50
STRONG_PER_CATEGORY = 100


def _load_from_files(paths: list[Path]) -> pd.DataFrame:
    """Auto-route files to parsers by filename prefix or content sniffing."""
    all_dtos = []
    for path in paths:
        source = _guess_source(path)
        parser = get_parser(source)
        with path.open("rb") as fh:
            all_dtos.extend(parser.parse(fh, filename=path.name))
    return dtos_to_dataframe(all_dtos)


def _guess_source(path: Path) -> BankSource:
    name = path.name.lower()
    if "pekao" in name or "pekaosa" in name:
        return BankSource.PEKAO
    if "revolut" in name or "account-statement" in name:
        return BankSource.REVOLUT
    raise ValueError(f"Cannot infer source for {path}")


def _load_synthetic(path: Path) -> pd.DataFrame:
    """Load a CSV produced by `finance.ml.classification.augment`."""
    df = pd.read_csv(path)
    required = {"text", "abs_amount", "day_of_week", "category"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Synthetic CSV missing columns: {missing}")
    df["source"] = df["source"].fillna("synthetic") if "source" in df.columns else "synthetic"
    return df


def _filter_rare_classes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    counts = df["category"].value_counts().to_dict()
    keep = {c for c, n in counts.items() if n >= MIN_PER_CLASS}
    dropped = {c: n for c, n in counts.items() if n < MIN_PER_CLASS}
    return df[df["category"].isin(keep)].reset_index(drop=True), dropped


def filter_category_training_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only confirmed rows that are valid expense-category training labels."""
    out = df[df["category"].notna()].copy() if "category" in df.columns else df.iloc[0:0]
    if out.empty:
        return out.reset_index(drop=True)
    out = out[expense_category_candidate_mask(out)]
    return out.reset_index(drop=True)


def build_label_readiness(df: pd.DataFrame) -> dict[str, object]:
    """Summarise whether confirmed labels are enough for reliable ML evidence."""
    labelled = filter_category_training_rows(df)
    counts = labelled["category"].astype(str).value_counts().to_dict() if not labelled.empty else {}
    category_counts = {category.value: int(counts.get(category.value, 0)) for category in Category}
    total = int(len(labelled))
    below_minimum = [
        category for category, count in category_counts.items() if count < MINIMUM_PER_CATEGORY
    ]
    below_recommended = [
        category
        for category, count in category_counts.items()
        if count < RECOMMENDED_PER_CATEGORY
    ]

    if total >= IDEAL_LABELLED_ROWS and not below_recommended:
        level = "thesis_ready"
    elif total >= RECOMMENDED_LABELLED_ROWS and not below_minimum:
        level = "good"
    elif total >= MINIMUM_LABELLED_ROWS:
        level = "minimum"
    else:
        level = "insufficient"

    date_span_months = None
    if "booking_date" in labelled.columns and not labelled.empty:
        dates = pd.to_datetime(labelled["booking_date"], errors="coerce").dropna()
        if not dates.empty:
            date_span_months = int(
                (dates.max().year - dates.min().year) * 12
                + dates.max().month
                - dates.min().month
                + 1
            )

    return {
        "level": level,
        "total_labelled": total,
        "minimum_total": MINIMUM_LABELLED_ROWS,
        "recommended_total": RECOMMENDED_LABELLED_ROWS,
        "ideal_total": IDEAL_LABELLED_ROWS,
        "minimum_per_category": MINIMUM_PER_CATEGORY,
        "recommended_per_category": RECOMMENDED_PER_CATEGORY,
        "strong_per_category": STRONG_PER_CATEGORY,
        "category_counts": category_counts,
        "below_minimum_per_category": below_minimum,
        "below_recommended_per_category": below_recommended,
        "date_span_months": date_span_months,
        "recommended_history_months": "6-12",
        "training_labels_source": "confirmed Transaction.category only",
        "category_predicted_is_ground_truth": False,
        "language_note": (
            "Polish real bank labels are the primary quality signal. English "
            "external datasets are experiment-only and may hurt Polish merchant "
            "generalisation."
        ),
        "next_review_priority": [
            "unlabelled expense-like rows",
            "low-confidence suggestions",
            "rare categories below target",
            "frequent merchants with repeated mistakes",
        ],
    }


def _cross_val_confidence(
    pipe,
    X: pd.DataFrame,  # noqa: N803
    y: pd.Series,
    cv,
) -> np.ndarray | None:
    """Best-effort out-of-fold confidence for threshold calibration.

    LinearSVC exposes margins, not calibrated probabilities. For thesis
    evidence we report them as a confidence proxy and explicitly describe that
    threshold tuning is empirical.
    """
    return cross_val_prediction_confidence(pipe, X, y, cv)


def _confidence_curve(
    y_true: pd.Series,
    y_pred: np.ndarray,
    confidence: np.ndarray | None,
) -> list[dict[str, float | int | None]]:
    if confidence is None:
        return [
            {
                "threshold": threshold,
                "coverage": None,
                "accuracy_on_covered": None,
                "covered": 0,
            }
            for threshold in CONFIDENCE_THRESHOLDS
        ]

    truth = np.asarray(y_true.astype(str))
    pred = np.asarray(y_pred.astype(str))
    out: list[dict[str, float | int | None]] = []
    for threshold in CONFIDENCE_THRESHOLDS:
        mask = confidence >= threshold
        covered = int(mask.sum())
        accuracy = float((truth[mask] == pred[mask]).mean()) if covered else None
        out.append(
            {
                "threshold": threshold,
                "coverage": float(covered / len(truth)),
                "accuracy_on_covered": accuracy,
                "covered": covered,
            }
        )
    return out


def _confidence_point(
    model_report: dict,
    threshold: float,
) -> dict[str, float | int | None]:
    curve = model_report.get("confidence_curve") or []
    for point in curve:
        if abs(float(point.get("threshold", -1.0)) - threshold) < 1e-9:
            return point
    return {
        "threshold": threshold,
        "coverage": None,
        "accuracy_on_covered": None,
        "covered": 0,
    }


def _per_category_metrics(report: dict, labels: list[str]) -> dict[str, dict[str, float | int]]:
    raw = report.get("report", {}) if "report" in report else report
    out: dict[str, dict[str, float | int]] = {}
    for label in labels:
        metrics = raw.get(label, {}) if isinstance(raw, dict) else {}
        out[label] = {
            "precision": float(metrics.get("precision", 0.0) or 0.0),
            "recall": float(metrics.get("recall", 0.0) or 0.0),
            "f1": float(metrics.get("f1-score", 0.0) or 0.0),
            "support": int(metrics.get("support", 0) or 0),
        }
    return out


def _confusion_hotspots_from_predictions(
    y_true: pd.Series,
    y_pred: np.ndarray,
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    truth = np.asarray(y_true.astype(str))
    pred = np.asarray(pd.Series(y_pred).astype(str))
    counts: dict[tuple[str, str], int] = {}
    for actual, predicted in zip(truth, pred, strict=False):
        if actual == predicted:
            continue
        key = (str(predicted), str(actual))
        counts[key] = counts.get(key, 0) + 1
    rows = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [
        {
            "predicted_category": predicted,
            "actual_category": actual,
            "count": count,
        }
        for (predicted, actual), count in rows
    ]


def _recommended_thresholds_by_category(
    y_true: pd.Series,
    y_pred: np.ndarray,
    confidence: np.ndarray | None,
    labels: list[str],
    *,
    target_accuracy: float = TARGET_THRESHOLD_ACCURACY,
) -> dict[str, dict[str, float | int | None]]:
    if confidence is None:
        return {
            label: {
                "threshold": EVIDENCE_THRESHOLD,
                "coverage": None,
                "accuracy_on_covered": None,
                "covered": 0,
            }
            for label in labels
        }
    truth = np.asarray(y_true.astype(str))
    pred = np.asarray(pd.Series(y_pred).astype(str))
    conf = np.asarray(confidence, dtype=float)
    out: dict[str, dict[str, float | int | None]] = {}
    for label in labels:
        predicted_label = pred == label
        total_predicted = int(predicted_label.sum())
        chosen: dict[str, float | int | None] | None = None
        for threshold in sorted(CONFIDENCE_THRESHOLDS):
            mask = predicted_label & (conf >= threshold)
            covered = int(mask.sum())
            if covered == 0:
                continue
            accuracy = float((truth[mask] == pred[mask]).mean())
            candidate = {
                "threshold": threshold,
                "coverage": float(covered / total_predicted) if total_predicted else 0.0,
                "accuracy_on_covered": accuracy,
                "covered": covered,
            }
            if accuracy >= target_accuracy:
                chosen = candidate
                break
            chosen = candidate
        out[label] = chosen or {
            "threshold": EVIDENCE_THRESHOLD,
            "coverage": 0.0,
            "accuracy_on_covered": None,
            "covered": 0,
        }
    return out


def _model_metrics_from_predictions(
    y: pd.Series,
    y_pred: np.ndarray,
    confidence: np.ndarray | None,
    labels: list[str],
) -> dict[str, object]:
    report = classification_report(
        y,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "macro_f1": f1_score(y, y_pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(y, y_pred, average="weighted", zero_division=0),
        "report": report,
        "labels": labels,
        "confusion_matrix": confusion_matrix(y, y_pred, labels=labels).tolist(),
        "confidence_curve": _confidence_curve(y, y_pred, confidence),
        "per_category": _per_category_metrics(report, labels),
        "confusion_hotspots": _confusion_hotspots_from_predictions(y, y_pred),
        "recommended_thresholds_by_category": _recommended_thresholds_by_category(
            y,
            y_pred,
            confidence,
            labels,
        ),
    }


def _best_non_dummy(report: dict, *, metric: str = "macro_f1") -> str | None:
    candidates = {
        name: info
        for name, info in report.get("models", {}).items()
        if not name.startswith("dummy") and not info.get("skipped")
    }
    if not candidates:
        return None
    return max(candidates, key=lambda name: float(candidates[name].get(metric, 0.0)))


def _feature_decision(
    baseline: dict,
    feature_v2: dict,
    *,
    threshold: float = EVIDENCE_THRESHOLD,
) -> dict[str, object]:
    """Compare baseline vs feature-v2 without mutating runtime choice."""
    base_model = _best_non_dummy(baseline)
    v2_model = _best_non_dummy(feature_v2)
    if base_model is None or v2_model is None:
        return {
            "recommended_feature_set": "baseline",
            "reason": "No comparable non-dummy models were available.",
            "threshold": threshold,
        }

    base = baseline["models"][base_model]
    v2 = feature_v2["models"][v2_model]
    base_curve = _confidence_point(base, threshold)
    v2_curve = _confidence_point(v2, threshold)
    base_macro = float(base.get("macro_f1", 0.0))
    v2_macro = float(v2.get("macro_f1", 0.0))
    base_accuracy = base_curve.get("accuracy_on_covered")
    v2_accuracy = v2_curve.get("accuracy_on_covered")
    base_coverage = base_curve.get("coverage")
    v2_coverage = v2_curve.get("coverage")

    macro_gain = v2_macro - base_macro
    accuracy_gain = (
        float(v2_accuracy) - float(base_accuracy)
        if isinstance(v2_accuracy, float) and isinstance(base_accuracy, float)
        else None
    )
    coverage_gain = (
        float(v2_coverage) - float(base_coverage)
        if isinstance(v2_coverage, float) and isinstance(base_coverage, float)
        else None
    )
    v2_wins = macro_gain >= 0.01 and (
        accuracy_gain is None or accuracy_gain >= -0.01
    )

    return {
        "recommended_feature_set": "feature_v2" if v2_wins else "baseline",
        "reason": (
            "feature_v2 improves macro-F1 without hurting threshold accuracy."
            if v2_wins
            else "Keep baseline until feature_v2 clearly improves macro-F1 and threshold accuracy."
        ),
        "threshold": threshold,
        "baseline": {
            "model": base_model,
            "macro_f1": base_macro,
            "coverage": base_coverage,
            "accuracy_on_covered": base_accuracy,
        },
        "feature_v2": {
            "model": v2_model,
            "macro_f1": v2_macro,
            "coverage": v2_coverage,
            "accuracy_on_covered": v2_accuracy,
        },
        "macro_f1_gain": macro_gain,
        "coverage_gain": coverage_gain,
        "accuracy_on_covered_gain": accuracy_gain,
    }


def evaluate(
    df: pd.DataFrame,
    *,
    n_splits: int = 5,
    seed: int = 42,
    pipeline_builder=build_pipeline,
    feature_selector=to_features,
) -> dict:
    df = filter_category_training_rows(df)
    if df.empty:
        raise SystemExit("No labelled rows to train on.")
    df, dropped = _filter_rare_classes(df)

    X = feature_selector(df)  # noqa: N806
    y = df["category"].astype(str)
    labels = sorted(y.unique())

    n_splits = min(n_splits, int(y.value_counts().min()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    results: dict[str, dict] = {}
    for name, factory in ESTIMATORS.items():
        pipe = pipeline_builder(factory())
        try:
            y_pred = cross_val_predict(pipe, X, y, cv=cv, n_jobs=None)
            confidence = _cross_val_confidence(pipe, X, y, cv)
            metrics = _model_metrics_from_predictions(y, y_pred, confidence, labels)
            results[name] = {
                **metrics,
                "confidence_note": (
                    "For LinearSVC this is a softmax-normalized decision margin, "
                    "not a calibrated probability. Calibrated estimators expose "
                    "predict_proba."
                ),
                "skipped": False,
            }
        except Exception as exc:  # noqa: BLE001
            results[name] = {
                "macro_f1": 0.0,
                "weighted_f1": 0.0,
                "report": {},
                "labels": labels,
                "confusion_matrix": [],
                "confidence_curve": _confidence_curve(y, np.asarray([], dtype=str), None),
                "confidence_note": "Estimator skipped because CV failed.",
                "skipped": True,
                "error": str(exc),
            }

    return {
        "n_total_labelled": int(len(df)),
        "n_classes": int(y.nunique()),
        "labels": labels,
        "class_counts": y.value_counts().to_dict(),
        "dropped_rare_classes": dropped,
        "n_splits": n_splits,
        "models": results,
    }


def evaluate_feature_v2(df: pd.DataFrame, *, n_splits: int = 5, seed: int = 42) -> dict:
    return evaluate(
        df,
        n_splits=n_splits,
        seed=seed,
        pipeline_builder=build_pipeline_v2,
        feature_selector=to_features_v2,
    )


def _predict_confidence_after_fit(pipe, X: pd.DataFrame) -> np.ndarray | None:  # noqa: N803
    vector = prediction_confidence_vector(pipe, X)
    if vector is None:
        return None
    _, confidences = vector
    if len(X) == 1:
        return np.asarray([float(np.max(confidences))])
    try:
        if hasattr(pipe, "predict_proba"):
            proba = np.asarray(pipe.predict_proba(X), dtype=float)
            return proba.max(axis=1)
        if hasattr(pipe, "decision_function"):
            scores = np.asarray(pipe.decision_function(X), dtype=float)
            if scores.ndim == 1:
                scores = np.column_stack([-scores, scores])
            scores = scores - scores.max(axis=1, keepdims=True)
            exp = np.exp(scores)
            proba = exp / exp.sum(axis=1, keepdims=True)
            return proba.max(axis=1)
    except Exception:
        return None
    return None


def _evaluate_holdout(
    df: pd.DataFrame,
    *,
    train_idx: pd.Index,
    test_idx: pd.Index,
    pipeline_builder=build_pipeline,
    feature_selector=to_features,
) -> dict[str, object]:
    train_df = filter_category_training_rows(df.loc[train_idx]).reset_index(drop=True)
    test_df = filter_category_training_rows(df.loc[test_idx]).reset_index(drop=True)
    if train_df.empty or test_df.empty:
        return {"skipped": True, "reason": "Empty train or test split."}
    train_df, dropped = _filter_rare_classes(train_df)
    train_labels = set(train_df["category"].astype(str))
    test_df = test_df[test_df["category"].astype(str).isin(train_labels)].reset_index(drop=True)
    if train_df.empty or test_df.empty or len(train_labels) < 2:
        return {
            "skipped": True,
            "reason": "Not enough overlapping classes in train/test split.",
            "dropped_rare_classes": dropped,
        }

    X_train = feature_selector(train_df)  # noqa: N806
    y_train = train_df["category"].astype(str)
    X_test = feature_selector(test_df)  # noqa: N806
    y_test = test_df["category"].astype(str)
    labels = sorted(set(y_train) | set(y_test))
    results: dict[str, dict[str, object]] = {}
    for name, factory in ESTIMATORS.items():
        pipe = pipeline_builder(factory())
        try:
            pipe.fit(X_train, y_train)
            y_pred = pipe.predict(X_test)
            confidence = _predict_confidence_after_fit(pipe, X_test)
            results[name] = {
                **_model_metrics_from_predictions(y_test, y_pred, confidence, labels),
                "skipped": False,
            }
        except Exception as exc:  # noqa: BLE001
            results[name] = {
                "macro_f1": 0.0,
                "weighted_f1": 0.0,
                "skipped": True,
                "error": str(exc),
            }
    return {
        "skipped": False,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "labels": labels,
        "dropped_rare_classes": dropped,
        "models": results,
    }


def _time_holdout(df: pd.DataFrame, *, test_fraction: float = 0.2) -> dict[str, object]:
    labelled = filter_category_training_rows(df)
    if labelled.empty or "booking_date" not in labelled.columns:
        return {"skipped": True, "reason": "No booking_date in labelled data."}
    ordered = labelled.sort_values("booking_date").reset_index(drop=True)
    split = max(int(len(ordered) * (1.0 - test_fraction)), 1)
    if split >= len(ordered):
        return {"skipped": True, "reason": "Not enough rows for time holdout."}
    return _evaluate_holdout(
        ordered,
        train_idx=ordered.index[:split],
        test_idx=ordered.index[split:],
    ) | {"split": "last_20_percent_by_booking_date"}


def _merchant_group_holdout(
    df: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    seed: int = 42,
) -> dict[str, object]:
    labelled = filter_category_training_rows(df)
    if labelled.empty:
        return {"skipped": True, "reason": "No labelled data."}
    merchant = labelled.get("merchant", labelled["text"]).fillna("").map(normalize_merchant)
    groups = merchant.where(merchant.str.len() > 0, labelled["text"].fillna(""))
    if groups.nunique() < 2:
        return {"skipped": True, "reason": "Not enough merchant groups."}
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=seed)
    train_pos, test_pos = next(splitter.split(labelled, labelled["category"], groups))
    train_groups = set(groups.iloc[train_pos])
    test_groups = set(groups.iloc[test_pos])
    overlap = train_groups & test_groups
    report = _evaluate_holdout(
        labelled.reset_index(drop=True),
        train_idx=pd.Index(train_pos),
        test_idx=pd.Index(test_pos),
    )
    if isinstance(report, dict):
        report["split"] = "group_shuffle_by_merchant_norm"
        report["merchant_group_overlap"] = len(overlap)
    return report


def build_validation_slices(
    real_df: pd.DataFrame,
    *,
    seed: int = 42,
) -> dict[str, object]:
    stratified = evaluate(real_df, seed=seed)
    return {
        "stratified_cv": stratified,
        "time_holdout": _time_holdout(real_df),
        "merchant_group_holdout": _merchant_group_holdout(real_df, seed=seed),
    }


def build_evidence_report(
    real_df: pd.DataFrame,
    *,
    augmented_df: pd.DataFrame | None = None,
    external_df: pd.DataFrame | None = None,
    n_splits: int = 5,
    seed: int = 42,
) -> dict:
    """Build thesis-oriented report: real-only plus optional extra datasets.

    The top level remains compatible with older ``classification_*.json``
    readers by exposing the selected experiment directly under ``models``.
    """
    label_readiness = build_label_readiness(real_df)
    experiments = {
        "real_only": evaluate(real_df, n_splits=n_splits, seed=seed),
    }
    external_summary: dict[str, object] = {"provided": external_df is not None}
    if external_df is not None:
        external_labelled = external_df[external_df["category"].notna()].reset_index(
            drop=True
        )
        external_summary.update(
            {
                "n_rows": int(len(external_df)),
                "n_labelled": int(len(external_labelled)),
                "class_counts": external_labelled["category"].value_counts().to_dict(),
            }
        )
        if not external_labelled.empty:
            experiments["external_only"] = evaluate(
                external_labelled,
                n_splits=n_splits,
                seed=seed,
            )
            experiments["real_plus_external"] = evaluate(
                pd.concat([real_df, external_labelled], ignore_index=True, sort=False),
                n_splits=n_splits,
                seed=seed,
            )

    feature_variants = {
        "baseline": experiments["real_only"],
        "feature_v2": evaluate_feature_v2(real_df, n_splits=n_splits, seed=seed),
    }
    feature_decision = _feature_decision(
        feature_variants["baseline"],
        feature_variants["feature_v2"],
    )
    validation_slices = build_validation_slices(real_df, seed=seed)
    selected = "real_only"
    if augmented_df is not None:
        combined = pd.concat([real_df, augmented_df], ignore_index=True, sort=False)
        experiments["augmented"] = evaluate(combined, n_splits=n_splits, seed=seed)

    report = dict(experiments[selected])
    best_model = _best_non_dummy(experiments["real_only"])
    best_report = (
        experiments["real_only"]["models"].get(best_model, {})
        if best_model is not None
        else {}
    )
    report.update(
        {
            "report_type": "classification_evidence",
            "selected_experiment": selected,
            "selected_experiment_note": (
                "real_only is the primary quality signal. Augmented/external "
                "experiments are reported separately and do not replace real labels."
            ),
            "experiments": experiments,
            "feature_variants": feature_variants,
            "feature_decision": feature_decision,
            "validation_slices": validation_slices,
            "confusion_hotspots": best_report.get("confusion_hotspots", []),
            "confidence_policy": {
                "source_model": best_model,
                "default_threshold": EVIDENCE_THRESHOLD,
                "target_accuracy": TARGET_THRESHOLD_ACCURACY,
                "per_category": best_report.get(
                    "recommended_thresholds_by_category",
                    {},
                ),
            },
            "feature_v2_note": (
                "Experimental comparison only. Runtime classifier_latest remains "
                "on the baseline feature set until reviewed."
            ),
            "label_readiness": label_readiness,
            "external_data": external_summary,
            "external_data_note": (
                "External public/synthetic datasets are reported as separate "
                "experiments. They do not replace real manually confirmed labels."
            ),
            "target_macro_f1": 0.75,
            "privacy_note": (
                "Report contains aggregate metrics only. Raw bank exports and "
                "model artifacts stay in gitignored data/raw, data/private and data/models."
            ),
        }
    )
    return report


def _feature_builder(feature_set: str):
    if feature_set == "baseline":
        return build_pipeline, to_features
    if feature_set == "feature_v2":
        return build_pipeline_v2, to_features_v2
    raise ValueError(f"Unknown feature_set: {feature_set}. Choose: {sorted(FEATURE_SETS)}")


def fit_final(
    df: pd.DataFrame,
    estimator_name: str,
    *,
    feature_set: str = DEFAULT_FEATURE_SET,
):
    df = filter_category_training_rows(df)
    df, _ = _filter_rare_classes(df)
    pipeline_builder, feature_selector = _feature_builder(feature_set)
    X = feature_selector(df)  # noqa: N806
    y = df["category"].astype(str)
    pipe = pipeline_builder(ESTIMATORS[estimator_name]())
    pipe.fit(X, y)
    return pipe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-files", nargs="+", type=Path)
    src.add_argument("--from-db", action="store_true")
    p.add_argument(
        "--persist",
        choices=list(ESTIMATORS.keys()),
        default=None,
        help="Refit on the full labelled set with this estimator and save it.",
    )
    p.add_argument(
        "--augment",
        type=Path,
        default=None,
        help="Optional CSV produced by augment.py. Concatenated with real data.",
    )
    p.add_argument(
        "--external-kaggle",
        type=Path,
        default=None,
        help=(
            "Optional Kaggle Personal_Finance_Dataset.csv. Reported as "
            "external_only and real_plus_external experiments."
        ),
    )
    p.add_argument(
        "--feature-set",
        choices=sorted(FEATURE_SETS),
        default=DEFAULT_FEATURE_SET,
        help=(
            "Feature set used only for --persist. Evidence still compares "
            "baseline vs feature_v2."
        ),
    )
    args = p.parse_args(argv)

    if args.from_db:
        from finance.db import SessionLocal

        with SessionLocal() as session:
            df = load_training_set(session)
    else:
        df = _load_from_files(list(args.from_files))

    print(f"Loaded {len(df)} rows total; "
          f"{df['category'].notna().sum()} labelled.")

    synth = None
    if args.augment is not None:
        synth = _load_synthetic(args.augment)
        print(f"  + augmented with {len(synth)} synthetic rows from {args.augment}")

    external = None
    if args.external_kaggle is not None:
        external = load_kaggle_personal_finance(args.external_kaggle)
        counts = external["category"].value_counts().to_dict()
        print(
            f"  + external Kaggle rows: {len(external)} labelled "
            f"from {args.external_kaggle}; classes={counts}"
        )

    report = build_evidence_report(df, augmented_df=synth, external_df=external)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORTS_DIR / f"classification_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\nSelected experiment: {report['selected_experiment']}")
    for exp_name, exp_report in report["experiments"].items():
        print(f"\nCV macro-F1 per estimator ({exp_name}):")
        for name, info in exp_report["models"].items():
            suffix = " skipped" if info.get("skipped") else ""
            print(
                f"  {name:20s}  macro_f1={info['macro_f1']:.3f}  "
                f"weighted_f1={info['weighted_f1']:.3f}{suffix}"
            )
    decision = report.get("feature_decision", {})
    print(
        "\nFeature-set recommendation: "
        f"{decision.get('recommended_feature_set', 'baseline')} "
        f"({decision.get('reason', 'n/a')})"
    )
    print(f"\nFull report -> {report_path}")

    if args.persist:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model = fit_final(df, args.persist, feature_set=args.feature_set)
        out = MODELS_DIR / f"classifier_{args.persist}_{ts}.joblib"
        artifact = {
            "estimator": args.persist,
            "feature_set": args.feature_set,
            "pipeline": model,
            "report": report,
        }
        joblib.dump(artifact, out)
        latest = MODELS_DIR / "classifier_latest.joblib"
        joblib.dump(artifact, latest)
        print(
            f"Persisted {args.persist}/{args.feature_set} -> {out} "
            f"(and {latest})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
