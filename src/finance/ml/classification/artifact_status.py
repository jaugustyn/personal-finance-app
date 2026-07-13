"""Status inspection for one explicitly selected classifier artifact."""
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
from finance.ml.classification.constants import DEFAULT_ACCEPT_THRESHOLD
from finance.ml.classification.status_io import iso_mtime


def _confidence_point(
    model_report: dict[str, Any], threshold: float = DEFAULT_ACCEPT_THRESHOLD
) -> tuple[float | None, float | None]:
    for point in model_report.get("confidence_curve") or []:
        if abs(float(point.get("threshold", -1.0)) - threshold) < 1e-9:
            coverage = point.get("coverage")
            accuracy = point.get("accuracy_on_covered")
            return (
                float(coverage) if coverage is not None else None,
                float(accuracy) if accuracy is not None else None,
            )
    return None, None


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


def empty_model_status() -> dict[str, Any]:
    """Return a status that contains no report or artifact-derived stale data."""
    known_categories = sorted(category.value for category in Category)
    return {
        "exists": False,
        "path": "",
        "updated_at": None,
        "model_version_id": None,
        "estimator": None,
        "feature_set": None,
        "classes": [],
        "known_categories": known_categories,
        "missing_categories": known_categories,
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


def model_status_from_disk(
    *,
    model_path: Path,
) -> dict[str, Any]:
    """Inspect only ``model_path``; never infer state from nearby report files."""
    status = empty_model_status()
    status["path"] = str(model_path)
    status["exists"] = model_path.exists()
    status["updated_at"] = iso_mtime(model_path)
    known_categories = status["known_categories"]

    if not model_path.exists():
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
        report_value = artifact.get("report")
        report = report_value if isinstance(report_value, dict) else None
        pipe = artifact.get("pipeline")
        status["model_version_id"] = artifact.get("model_version_id")
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

    observed = set(status["classes"])
    known = set(known_categories)
    status["missing_categories"] = sorted(known - observed)
    status["extra_classes"] = sorted(observed - known)
    return status
