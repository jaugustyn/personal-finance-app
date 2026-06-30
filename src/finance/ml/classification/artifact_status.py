"""Classifier artifact status inspection."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import joblib

from finance.domain.enums import Category
from finance.ml.classification.artifacts import (
    artifact_metadata,
    compatibility_warnings,
)
from finance.ml.classification.constants import MODEL_PATH, REPORTS_DIR
from finance.ml.classification.status_comparison import confidence_point
from finance.ml.classification.status_io import iso_mtime, load_latest_report


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
    coverage, accuracy = confidence_point(best)
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
