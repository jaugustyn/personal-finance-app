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

from finance.ml.classification.pipeline import FEATURE_V2_COLUMNS, REQUIRED_COLUMNS

MODEL_ARTIFACT_SCHEMA_VERSION = "2.1"


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
        "confidence_policy": confidence_policy or {},
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
