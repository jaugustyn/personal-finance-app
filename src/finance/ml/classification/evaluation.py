"""Evaluation helpers for the expense-category classifier."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit, StratifiedKFold, cross_val_predict

from finance.analytics.filters import expense_category_candidate_mask
from finance.domain.enums import (
    CATEGORY_CONFIRMATION_METHOD_VALUES,
    CATEGORY_VALUES,
    Category,
)
from finance.ml.classification.confidence import (
    cross_val_prediction_confidence,
    prediction_confidence_vector,
)
from finance.ml.classification.constants import (
    CONFIDENCE_THRESHOLDS,
    EVIDENCE_THRESHOLD,
    IDEAL_LABELLED_ROWS,
    MIN_PER_CLASS,
    MINIMUM_LABELLED_ROWS,
    MINIMUM_PER_CATEGORY,
    RECOMMENDED_LABELLED_ROWS,
    RECOMMENDED_PER_CATEGORY,
    STRONG_PER_CATEGORY,
    TARGET_THRESHOLD_ACCURACY,
)
from finance.ml.classification.exceptions import (
    InsufficientClassSupport,
    NoLabelledRows,
)
from finance.ml.classification.pipeline import (
    build_pipeline,
    build_pipeline_v2,
    to_features,
    to_features_v2,
)
from finance.ml.classification.registry import ESTIMATORS
from finance.transactions.merchants import merchant_canonical_key


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
    out = out[out["category"].astype(str).isin(CATEGORY_VALUES)]
    if "category_confirmation_method" in out.columns:
        out = out[
            out["category_confirmation_method"].isin(CATEGORY_CONFIRMATION_METHOD_VALUES)
        ]
    if "category_confirmed_at" in out.columns:
        out = out[out["category_confirmed_at"].notna()]
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

    date_span_months = None
    date_span_days = 0
    calendar_months = 0
    if "booking_date" in labelled.columns and not labelled.empty:
        dates = pd.to_datetime(labelled["booking_date"], errors="coerce").dropna()
        if not dates.empty:
            calendar_months = int(dates.dt.to_period("M").nunique())
            date_span_days = int((dates.max() - dates.min()).days) if len(dates) > 1 else 0
            date_span_months = int(
                (dates.max().year - dates.min().year) * 12
                + dates.max().month
                - dates.min().month
                + 1
            )

    technical_ready = total >= MINIMUM_LABELLED_ROWS
    thesis_data_ready = (
        total >= RECOMMENDED_LABELLED_ROWS
        and not below_recommended
        and calendar_months >= 12
        and date_span_days >= 365
    )
    level = (
        "thesis_data_ready"
        if thesis_data_ready
        else "technical_ready"
        if technical_ready
        else "insufficient"
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
        "calendar_months": calendar_months,
        "date_span_days": date_span_days,
        "technical_ready": technical_ready,
        "thesis_data_ready": thesis_data_ready,
        "recommended_history_months": "12+",
        "training_labels_source": (
            "explicitly confirmed 9-class expense Transaction.category only"
        ),
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


def _cross_val_confidence(pipe, X: pd.DataFrame, y: pd.Series, cv) -> np.ndarray | None:  # noqa: N803
    """Best-effort out-of-fold confidence for threshold calibration."""
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
            candidate: dict[str, float | int | None] = {
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
        raise NoLabelledRows("No labelled rows to train on.")
    df, dropped = _filter_rare_classes(df)

    X = feature_selector(df)  # noqa: N806
    y = df["category"].astype(str)
    labels = sorted(y.unique())
    if y.nunique() < 2:
        raise InsufficientClassSupport("At least two category classes are required.")

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


def evaluate_extra_training_only(
    real_df: pd.DataFrame,
    extra_df: pd.DataFrame,
    *,
    n_splits: int = 5,
    seed: int = 42,
) -> dict[str, object]:
    """Add synthetic/external rows only to training folds; score real rows only."""
    real = filter_category_training_rows(real_df)
    real, dropped = _filter_rare_classes(real)
    if real.empty or real["category"].nunique() < 2:
        raise InsufficientClassSupport("Real data needs at least two supported classes.")
    extra = extra_df[extra_df["category"].notna()].copy()
    labels = sorted(real["category"].astype(str).unique())
    extra = extra[extra["category"].astype(str).isin(labels)].reset_index(drop=True)
    y = real["category"].astype(str).reset_index(drop=True)
    real = real.reset_index(drop=True)
    n_splits = min(n_splits, int(y.value_counts().min()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    results: dict[str, dict[str, object]] = {}
    for name, factory in ESTIMATORS.items():
        predicted: np.ndarray = np.empty(len(real), dtype=object)
        confidence: np.ndarray = np.zeros(len(real), dtype=float)
        confidence_available = True
        try:
            for train_idx, test_idx in cv.split(real, y):
                train = pd.concat(
                    [real.iloc[train_idx], extra], ignore_index=True, sort=False
                )
                pipe = build_pipeline(factory())
                pipe.fit(to_features(train), train["category"].astype(str))
                X_test = to_features(real.iloc[test_idx])  # noqa: N806
                predicted[test_idx] = pipe.predict(X_test)
                fold_confidence = _predict_confidence_after_fit(pipe, X_test)
                if fold_confidence is None:
                    confidence_available = False
                else:
                    confidence[test_idx] = fold_confidence
            results[name] = {
                **_model_metrics_from_predictions(
                    y,
                    predicted,
                    confidence if confidence_available else None,
                    labels,
                ),
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
        "n_total_labelled": int(len(real)),
        "n_extra_training_rows": int(len(extra)),
        "n_classes": len(labels),
        "labels": labels,
        "class_counts": y.value_counts().to_dict(),
        "dropped_rare_classes": dropped,
        "n_splits": n_splits,
        "evaluation_rows": "real_only",
        "extra_rows_role": "training_folds_only",
        "models": results,
    }


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


def _time_holdout(
    df: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    pipeline_builder=build_pipeline,
    feature_selector=to_features,
) -> dict[str, object]:
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
        pipeline_builder=pipeline_builder,
        feature_selector=feature_selector,
    ) | {"split": "last_20_percent_by_booking_date"}


def _merchant_group_holdout(
    df: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    seed: int = 42,
    pipeline_builder=build_pipeline,
    feature_selector=to_features,
) -> dict[str, object]:
    labelled = filter_category_training_rows(df)
    if labelled.empty:
        return {"skipped": True, "reason": "No labelled data."}
    merchant = labelled.get("merchant", labelled["text"]).fillna("")
    title = labelled.get("title", labelled["text"]).fillna("")
    groups = pd.Series(
        [
            merchant_canonical_key(merchant_value, title_value)
            for merchant_value, title_value in zip(merchant, title, strict=False)
        ],
        index=labelled.index,
    )
    groups = groups.where(groups.str.len() > 0, labelled["text"].fillna(""))
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
        pipeline_builder=pipeline_builder,
        feature_selector=feature_selector,
    )
    if isinstance(report, dict):
        report["split"] = "group_shuffle_by_merchant_canonical"
        report["merchant_group_overlap"] = len(overlap)
    return report


def build_validation_slices(
    real_df: pd.DataFrame,
    *,
    seed: int = 42,
    pipeline_builder=build_pipeline,
    feature_selector=to_features,
) -> dict[str, object]:
    stratified = evaluate(
        real_df,
        seed=seed,
        pipeline_builder=pipeline_builder,
        feature_selector=feature_selector,
    )
    return {
        "stratified_cv": stratified,
        "time_holdout": _time_holdout(
            real_df,
            pipeline_builder=pipeline_builder,
            feature_selector=feature_selector,
        ),
        "merchant_group_holdout": _merchant_group_holdout(
            real_df,
            seed=seed,
            pipeline_builder=pipeline_builder,
            feature_selector=feature_selector,
        ),
    }
