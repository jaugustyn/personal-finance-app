"""Classifier status, report comparison and dashboard helpers."""
from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy.orm import Session

from finance.domain.enums import Category
from finance.ml.classification.artifacts import (
    artifact_metadata,
    compatibility_warnings,
)
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.train import build_label_readiness
from finance.ml.feedback import confusion_hotspots, feedback_quality, feedback_report

MODEL_PATH = Path("data/models/classifier_latest.joblib")
REPORTS_DIR = Path("data/reports")
CONFIDENCE_RECOMMENDATION_THRESHOLD = 0.55
DEFAULT_RECOMMENDED_ESTIMATOR = "linear_svc_calibrated"
DEFAULT_RECOMMENDED_FEATURE_SET = "feature_v2"
CALIBRATED_ESTIMATORS = {"linear_svc_calibrated", "logreg"}
RETRAIN_LABEL_GROWTH_THRESHOLD = 0.20
RETRAIN_FEEDBACK_EVENTS_THRESHOLD = 25
RETRAIN_REJECTION_RATE_THRESHOLD = 0.35
RETRAIN_REJECTION_MIN_EVENTS = 10


def iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_report_path(reports_dir: Path = REPORTS_DIR) -> Path | None:
    reports = sorted(reports_dir.glob("classification_*.json"))
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)


def load_latest_report(reports_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    path = latest_report_path(reports_dir)
    if path is None:
        return {"path": None, "updated_at": None, "report": None}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report = {"error": str(exc)}
    return {
        "path": str(path),
        "updated_at": iso_mtime(path),
        "report": report,
    }


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence_point(
    model_report: dict[str, Any],
    threshold: float = CONFIDENCE_RECOMMENDATION_THRESHOLD,
) -> tuple[float | None, float | None]:
    for point in model_report.get("confidence_curve") or []:
        if abs(float(point.get("threshold", -1.0)) - threshold) < 1e-9:
            return (
                _as_float(point.get("coverage")),
                _as_float(point.get("accuracy_on_covered")),
            )
    return None, None


def _iter_model_reports(
    report: dict[str, Any] | None,
) -> list[tuple[str, str, dict[str, Any]]]:
    if not report:
        return []
    out: list[tuple[str, str, dict[str, Any]]] = []
    feature_variants = report.get("feature_variants")
    if isinstance(feature_variants, dict):
        for feature_set, feature_report in feature_variants.items():
            if not isinstance(feature_report, dict):
                continue
            models = feature_report.get("models") or {}
            if not isinstance(models, dict):
                continue
            for estimator, model_report in models.items():
                if isinstance(model_report, dict):
                    out.append((str(feature_set), str(estimator), model_report))
    if out:
        return out

    models = report.get("models") or {}
    if isinstance(models, dict):
        for estimator, model_report in models.items():
            if isinstance(model_report, dict):
                out.append(("baseline", str(estimator), model_report))
    return out


def _recommended_feature_set(
    report: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not report:
        return None, None
    decision = report.get("feature_decision")
    if not isinstance(decision, dict):
        return None, None
    feature_set = decision.get("recommended_feature_set")
    raw_reason = decision.get("reason")
    reason = raw_reason if isinstance(raw_reason, str) else None
    if feature_set not in {"baseline", "feature_v2"}:
        return None, reason
    return str(feature_set), reason


def _slice_macro_f1(
    report: dict[str, Any] | None,
    slice_name: str,
    estimator: str,
) -> float | None:
    if not report:
        return None
    validation = report.get("validation_slices")
    if not isinstance(validation, dict):
        return None
    slice_report = validation.get(slice_name)
    if not isinstance(slice_report, dict) or slice_report.get("skipped"):
        return None
    models = slice_report.get("models")
    if not isinstance(models, dict):
        return None
    model = models.get(estimator)
    if not isinstance(model, dict) or model.get("skipped"):
        return None
    return _as_float(model.get("macro_f1"))


def _stability_score(
    report: dict[str, Any] | None,
    estimator: str,
) -> tuple[float | None, float | None, float | None]:
    time_macro = _slice_macro_f1(report, "time_holdout", estimator)
    group_macro = _slice_macro_f1(report, "merchant_group_holdout", estimator)
    values = [value for value in (time_macro, group_macro) if value is not None]
    score = sum(values) / len(values) if values else None
    return time_macro, group_macro, score


def model_comparison(
    report: dict[str, Any] | None,
    status: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    current_estimator = status.get("estimator") if status else None
    current_feature_set = (status.get("feature_set") or "baseline") if status else None
    rows: list[dict[str, Any]] = []
    for feature_set, estimator, model_report in _iter_model_reports(report):
        coverage, accuracy = _confidence_point(model_report)
        time_macro, group_macro, stability = _stability_score(report, estimator)
        rows.append(
            {
                "estimator": estimator,
                "feature_set": feature_set,
                "rank": None,
                "macro_f1": _as_float(model_report.get("macro_f1")),
                "weighted_f1": _as_float(model_report.get("weighted_f1")),
                "coverage_at_055": coverage,
                "accuracy_at_055": accuracy,
                "time_holdout_macro_f1": time_macro,
                "merchant_group_macro_f1": group_macro,
                "stability_score": stability,
                "confidence_note": model_report.get("confidence_note"),
                "skipped": bool(model_report.get("skipped")),
                "error": model_report.get("error"),
                "is_recommended": False,
                "is_current": (
                    estimator == current_estimator and feature_set == current_feature_set
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row["skipped"],
            -(row["stability_score"] or 0.0),
            -(row["macro_f1"] or 0.0),
            -(row["weighted_f1"] or 0.0),
            row["feature_set"],
            row["estimator"],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def recommend_model(
    report: dict[str, Any] | None,
    comparison: list[dict[str, Any]],
    status: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    actionable = [
        row
        for row in comparison
        if not row["skipped"] and not str(row["estimator"]).startswith("dummy")
    ]
    target_feature_set, feature_reason = _recommended_feature_set(report)

    if not actionable:
        recommendation = {
            "estimator": DEFAULT_RECOMMENDED_ESTIMATOR,
            "feature_set": target_feature_set or DEFAULT_RECOMMENDED_FEATURE_SET,
            "reason_code": "no_report",
            "action_codes": ["train_recommended"],
            "warning_codes": ["no_report"],
            "macro_f1": None,
            "weighted_f1": None,
            "coverage_at_055": None,
            "accuracy_at_055": None,
            "confidence_threshold": CONFIDENCE_RECOMMENDATION_THRESHOLD,
            "based_on_report": False,
            "feature_decision_reason": feature_reason,
        }
    else:
        pool = (
            [row for row in actionable if row["feature_set"] == target_feature_set]
            if target_feature_set
            else []
        )
        if not pool:
            pool = actionable

        best = max(
            pool,
            key=lambda row: (
                row["stability_score"] if row["stability_score"] is not None else -1.0,
                row["macro_f1"] or 0.0,
            ),
        )
        best_macro = best["macro_f1"] or 0.0
        calibrated_pool = [
            row
            for row in pool
            if row["estimator"] in CALIBRATED_ESTIMATORS
            and (row["macro_f1"] or 0.0) >= best_macro - 0.02
        ]
        if calibrated_pool:
            selected = max(
                calibrated_pool,
                key=lambda row: (
                    row["stability_score"]
                    if row["stability_score"] is not None
                    else -1.0,
                    row["macro_f1"] or 0.0,
                ),
            )
            reason_code = (
                "best_calibrated_macro_f1"
                if selected["estimator"] == best["estimator"]
                else "prefer_calibrated_close"
            )
        else:
            selected = best
            reason_code = "best_macro_f1"

        recommendation = {
            "estimator": selected["estimator"],
            "feature_set": selected["feature_set"],
            "reason_code": reason_code,
            "action_codes": [],
            "warning_codes": [],
            "macro_f1": selected["macro_f1"],
            "weighted_f1": selected["weighted_f1"],
            "coverage_at_055": selected["coverage_at_055"],
            "accuracy_at_055": selected["accuracy_at_055"],
            "confidence_threshold": CONFIDENCE_RECOMMENDATION_THRESHOLD,
            "based_on_report": True,
            "feature_decision_reason": feature_reason,
        }

    for row in comparison:
        row["is_recommended"] = (
            row["estimator"] == recommendation["estimator"]
            and row["feature_set"] == recommendation["feature_set"]
        )

    status_feature_set = status.get("feature_set") or "baseline"
    if (
        not status.get("exists")
        or status.get("load_error")
        or status.get("estimator") != recommendation["estimator"]
        or status_feature_set != recommendation["feature_set"]
        or status.get("compatibility_warnings")
    ):
        recommendation["action_codes"].append("train_recommended")
    else:
        recommendation["action_codes"].append("current_matches_recommended")

    recommendation["action_codes"].append("reclassify_after_training")

    if readiness.get("below_recommended_per_category"):
        recommendation["action_codes"].append("balance_categories")
    if status.get("missing_categories"):
        recommendation["warning_codes"].append("missing_categories")
    if readiness.get("level") in {"insufficient", "minimum"}:
        recommendation["warning_codes"].append("limited_labels")
    if status.get("compatibility_warnings"):
        recommendation["warning_codes"].append("artifact_compatibility")
    if not report:
        recommendation["warning_codes"].append("no_report")

    recommendation["action_codes"] = list(dict.fromkeys(recommendation["action_codes"]))
    recommendation["warning_codes"] = list(dict.fromkeys(recommendation["warning_codes"]))
    return recommendation


def _best_metric_summary(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    models = report.get("models") or {}
    candidates = {
        name: info
        for name, info in models.items()
        if not name.startswith("dummy") and not info.get("skipped")
    }
    if not candidates:
        return None
    best_name = max(
        candidates,
        key=lambda name: float(candidates[name].get("macro_f1") or 0.0),
    )
    best = candidates[best_name]
    coverage, accuracy = _confidence_point(best)
    return {
        "model": best_name,
        "macro_f1": best.get("macro_f1"),
        "weighted_f1": best.get("weighted_f1"),
        "coverage_at_055": coverage,
        "accuracy_at_055": accuracy,
    }


def _extract_model_classes(pipe: Any, report: dict[str, Any] | None) -> list[str]:
    named_steps = getattr(pipe, "named_steps", {}) if pipe is not None else {}
    clf = named_steps.get("clf") if isinstance(named_steps, dict) else None
    raw_classes = getattr(clf, "classes_", None)
    classes = list(raw_classes) if raw_classes is not None else []
    if not classes and report:
        classes = list(report.get("labels") or [])
    return sorted(str(item) for item in classes)


def model_status_from_disk(
    *,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    known_categories = sorted(category.value for category in Category)
    status: dict[str, Any] = {
        "exists": model_path.exists(),
        "path": str(model_path),
        "updated_at": iso_mtime(model_path),
        "estimator": None,
        "feature_set": None,
        "classes": [],
        "known_categories": known_categories,
        "missing_categories": [],
        "extra_classes": [],
        "n_total_labelled": None,
        "n_classes": None,
        "report_path": None,
        "report_updated_at": None,
        "best_model": None,
        "load_error": None,
        "artifact_metadata": {},
        "compatibility_warnings": [],
        "retrain_signal": None,
    }
    latest_report = load_latest_report(reports_dir)
    latest_report_data = (
        latest_report["report"] if isinstance(latest_report["report"], dict) else None
    )

    if not model_path.exists():
        status["report_path"] = latest_report["path"]
        status["report_updated_at"] = latest_report["updated_at"]
        status["best_model"] = _best_metric_summary(latest_report_data)
        status["missing_categories"] = known_categories
        return status

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            artifact = joblib.load(model_path)
        load_warnings = [
            warning.category.__name__
            for warning in caught
            if warning.category.__name__.endswith("Warning")
        ]
        if not isinstance(artifact, dict):
            raise TypeError("Invalid classifier artifact; expected metadata dict.")
        report = artifact.get("report")
        report = report if isinstance(report, dict) else latest_report_data
        pipe = artifact.get("pipeline")
        status["estimator"] = artifact.get("estimator")
        status["feature_set"] = artifact.get("feature_set")
        status["classes"] = _extract_model_classes(pipe, report)
        status["n_total_labelled"] = report.get("n_total_labelled") if report else None
        status["n_classes"] = report.get("n_classes") if report else None
        status["best_model"] = _best_metric_summary(report)
        status["artifact_metadata"] = artifact_metadata(artifact)
        compatibility = compatibility_warnings(status["artifact_metadata"])
        if "InconsistentVersionWarning" in load_warnings:
            compatibility.append("sklearn_unpickle_version_warning")
        status["compatibility_warnings"] = list(dict.fromkeys(compatibility))
    except Exception as exc:  # noqa: BLE001
        status["load_error"] = str(exc)
        if latest_report_data:
            status["classes"] = sorted(
                str(item) for item in latest_report_data.get("labels") or []
            )
            status["n_total_labelled"] = latest_report_data.get("n_total_labelled")
            status["n_classes"] = latest_report_data.get("n_classes")
        status["best_model"] = _best_metric_summary(latest_report_data)

    observed = set(status["classes"])
    known = set(known_categories)
    status["missing_categories"] = sorted(known - observed)
    status["extra_classes"] = sorted(observed - known)
    status["report_path"] = latest_report["path"]
    status["report_updated_at"] = latest_report["updated_at"]
    return status


def readiness_summary(session: Session) -> dict[str, Any]:
    df = load_training_set(session)
    return dict(build_label_readiness(df))


def retrain_signal(
    session: Session,
    status: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    model_updated_at = _parse_iso_datetime(status.get("updated_at"))
    report = feedback_report(
        session,
        model_updated_at=model_updated_at,
        labels_used_in_current_model=status.get("n_total_labelled"),
        current_label_count=readiness.get("total_labelled"),
    )
    quality = report["quality"]
    new_labels = int(report["new_labels_since_training"] or 0)
    label_growth_ratio = report["new_labels_since_training_ratio"]
    feedback_since_model = int(report["feedback_events_since_model"] or 0)
    rejection_rate = quality.get("rejection_rate")
    suggestion_feedback_total = int(quality.get("suggestion_feedback_total") or 0)

    reasons: list[str] = []
    if (
        label_growth_ratio is not None
        and label_growth_ratio >= RETRAIN_LABEL_GROWTH_THRESHOLD
        and new_labels > 0
    ):
        reasons.append("label_growth_since_training")
    if feedback_since_model >= RETRAIN_FEEDBACK_EVENTS_THRESHOLD:
        reasons.append("feedback_since_training")
    if (
        rejection_rate is not None
        and rejection_rate >= RETRAIN_REJECTION_RATE_THRESHOLD
        and suggestion_feedback_total >= RETRAIN_REJECTION_MIN_EVENTS
    ):
        reasons.append("high_rejection_rate")

    return {
        "retrain_recommended": bool(reasons),
        "reason_codes": reasons,
        "model_updated_at": status.get("updated_at"),
        "labels_used_in_current_model": status.get("n_total_labelled"),
        "current_label_count": readiness.get("total_labelled"),
        "new_labels_since_training": new_labels,
        "new_labels_since_training_ratio": label_growth_ratio,
        "feedback_events_since_model": feedback_since_model,
        "rejection_rate": rejection_rate,
        "suggestion_feedback_total": suggestion_feedback_total,
    }


def comparison_summary(
    session: Session,
    *,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    status = model_status_from_disk(model_path=model_path, reports_dir=reports_dir)
    readiness = readiness_summary(session)
    status["retrain_signal"] = retrain_signal(session, status, readiness)
    latest = load_latest_report(reports_dir)
    report = latest["report"] if isinstance(latest["report"], dict) else None
    comparison = model_comparison(report, status)
    return {
        "models": comparison,
        "recommendation": recommend_model(report, comparison, status, readiness),
    }


def dashboard_summary(
    session: Session,
    *,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    status = model_status_from_disk(model_path=model_path, reports_dir=reports_dir)
    readiness = readiness_summary(session)
    signal = retrain_signal(session, status, readiness)
    status["retrain_signal"] = signal
    latest = load_latest_report(reports_dir)
    report = latest["report"] if isinstance(latest["report"], dict) else None
    comparison = model_comparison(report, status)
    return {
        "status": status,
        "readiness": readiness,
        "latest_report": latest,
        "model_comparison": comparison,
        "recommendation": recommend_model(report, comparison, status, readiness),
        "validation_slices": report.get("validation_slices", {}) if report else {},
        "confidence_policy": report.get("confidence_policy", {}) if report else {},
        "feedback_quality": feedback_quality(session),
        "feedback_report": feedback_report(
            session,
            model_updated_at=_parse_iso_datetime(status.get("updated_at")),
            labels_used_in_current_model=status.get("n_total_labelled"),
            current_label_count=readiness.get("total_labelled"),
        ),
        "retrain_signal": signal,
        "confusion_hotspots": confusion_hotspots(session),
    }
