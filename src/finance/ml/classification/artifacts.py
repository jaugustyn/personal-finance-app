"""Classifier artifact metadata and compatibility helpers."""
from __future__ import annotations

import hashlib
import platform
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from finance.ml.classification.constants import DEFAULT_ACCEPT_THRESHOLD
from finance.ml.classification.pipeline import FEATURE_V2_COLUMNS, REQUIRED_COLUMNS

MODEL_ARTIFACT_SCHEMA_VERSION = "3.0"
RUNTIME_ESTIMATORS = {"logreg", "linear_svc_calibrated"}
RUNTIME_FEATURE_SET = "baseline"
RUNTIME_CONFIDENCE_POLICY = {
    "source": "fixed_runtime_threshold",
    "default_threshold": DEFAULT_ACCEPT_THRESHOLD,
    "per_category": {},
    "allow_other_accept": False,
}


def artifact_sha256(path: Path) -> str:
    """Return the checksum used by the model registry and runtime loader."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_versions() -> dict[str, str]:
    """Return versions that affect persisted sklearn pipeline compatibility."""
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "sklearn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "joblib": joblib.__version__,
    }


def build_model_artifact(
    *,
    estimator: str,
    feature_set: str,
    pipeline: Any,
    report: dict[str, Any],
    model_version_id: str | None = None,
    dataset_fingerprint: str | None = None,
    evaluation_set_id: str | None = None,
    confidence_policy: dict[str, Any] | None = None,
    confidence_diagnostics: dict[str, Any] | None = None,
    ontology_version: str = "category_v1",
) -> dict[str, Any]:
    """Build the persisted classifier artifact with explicit runtime metadata."""
    required_columns = (
        FEATURE_V2_COLUMNS if feature_set == "feature_v2" else REQUIRED_COLUMNS
    )
    return {
        "schema_version": MODEL_ARTIFACT_SCHEMA_VERSION,
        "task": "category",
        "estimator": estimator,
        "feature_set": feature_set,
        "pipeline": pipeline,
        "classes": [str(value) for value in getattr(pipeline, "classes_", [])],
        "feature_schema": {
            "name": feature_set,
            "required_columns": list(required_columns),
        },
        "report": report,
        "model_version_id": model_version_id,
        "dataset_fingerprint": dataset_fingerprint,
        "evaluation_set_id": evaluation_set_id,
        "ontology_version": ontology_version,
        "confidence_policy": confidence_policy or dict(RUNTIME_CONFIDENCE_POLICY),
        "confidence_diagnostics": confidence_diagnostics or {},
        "metadata": {
            "artifact_schema_version": MODEL_ARTIFACT_SCHEMA_VERSION,
            "runtime_versions": runtime_versions(),
        },
    }


def artifact_metadata(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return {}
    metadata = artifact.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def compatibility_warnings(
    metadata: dict[str, Any],
    *,
    current_versions: dict[str, str] | None = None,
) -> list[str]:
    """Return warning codes for model artifact/runtime mismatches."""
    if not metadata:
        return ["missing_artifact_metadata"]

    warnings: list[str] = []
    current = current_versions or runtime_versions()
    artifact_schema = metadata.get("artifact_schema_version")
    if artifact_schema != MODEL_ARTIFACT_SCHEMA_VERSION:
        warnings.append("artifact_schema_version_mismatch")

    versions = metadata.get("runtime_versions")
    if not isinstance(versions, dict):
        return [*warnings, "missing_runtime_versions"]

    for package in ("sklearn", "pandas", "numpy", "joblib"):
        saved = versions.get(package)
        current_value = current.get(package)
        if saved and current_value and str(saved) != str(current_value):
            warnings.append(f"{package}_version_mismatch")
        elif not saved:
            warnings.append(f"missing_{package}_version")

    saved_python = str(versions.get("python") or "")
    current_python = current.get("python", sys.version.split()[0])
    if saved_python and saved_python.split(".")[:2] != current_python.split(".")[:2]:
        warnings.append("python_minor_version_mismatch")
    elif not saved_python:
        warnings.append("missing_python_version")

    return warnings


def require_compatible_artifact(
    artifact: Any,
    *,
    current_versions: dict[str, str] | None = None,
) -> None:
    """Reject artifacts that differ from the locked runtime environment."""
    warnings = compatibility_warnings(
        artifact_metadata(artifact), current_versions=current_versions
    )
    if warnings:
        raise ValueError("Incompatible classifier artifact: " + ", ".join(warnings))
    if not isinstance(artifact, dict) or artifact.get("schema_version") != (
        MODEL_ARTIFACT_SCHEMA_VERSION
    ):
        raise ValueError("Incompatible classifier artifact: artifact_schema_version_mismatch")


def require_runtime_artifact(artifact: Any) -> None:
    """Reject compatible artifacts that do not implement the simplified runtime."""
    require_compatible_artifact(artifact)
    if not isinstance(artifact, dict) or artifact.get("task") != "category":
        raise ValueError("Incompatible classifier artifact: task_mismatch")
    if artifact.get("estimator") not in RUNTIME_ESTIMATORS:
        raise ValueError("Incompatible classifier artifact: estimator_not_promotable")
    if artifact.get("feature_set") != RUNTIME_FEATURE_SET:
        raise ValueError("Incompatible classifier artifact: feature_set_not_promotable")
    policy = artifact.get("confidence_policy")
    if not isinstance(policy, dict):
        raise ValueError("Incompatible classifier artifact: missing_confidence_policy")
    raw_threshold = policy.get("default_threshold")
    threshold = (
        float(raw_threshold) if isinstance(raw_threshold, int | float | str) else -1.0
    )
    if (
        threshold != DEFAULT_ACCEPT_THRESHOLD
        or policy.get("per_category") not in ({}, None)
        or policy.get("allow_other_accept") is not False
    ):
        raise ValueError("Incompatible classifier artifact: runtime_policy_mismatch")
