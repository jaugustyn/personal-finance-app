"""Classifier artifact metadata and compatibility helpers."""
from __future__ import annotations

import platform
import sys
from typing import Any

import numpy as np
import pandas as pd
import sklearn

MODEL_ARTIFACT_SCHEMA_VERSION = "1.0"


def runtime_versions() -> dict[str, str]:
    """Return versions that affect persisted sklearn pipeline compatibility."""
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "sklearn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }


def build_model_artifact(
    *,
    estimator: str,
    feature_set: str,
    pipeline: Any,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Build the persisted classifier artifact with explicit runtime metadata."""
    return {
        "schema_version": MODEL_ARTIFACT_SCHEMA_VERSION,
        "estimator": estimator,
        "feature_set": feature_set,
        "pipeline": pipeline,
        "report": report,
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

    for package in ("sklearn", "pandas", "numpy"):
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
