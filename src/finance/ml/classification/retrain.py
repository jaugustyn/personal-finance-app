"""Legacy offline retraining compatibility use case.

It writes an unregistered research artifact and is not used by the FastAPI model
registry. Runtime candidate jobs live in ``classification.lifecycle``.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from finance.ml.classification.artifacts import build_model_artifact
from finance.ml.classification.constants import MIN_RETRAIN_LABELLED_ROWS
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.fitting import fit_final
from finance.ml.classification.reports import build_evidence_report


@dataclass(frozen=True)
class RetrainResult:
    status: str
    labelled_rows: int
    model_path: Path | None = None
    report_path: Path | None = None
    message: str | None = None


def retrain_classifier(
    *,
    session_factory: Callable[[], Session],
    estimator: str,
    feature_set: str,
    model_path: Path,
    reports_dir: Path,
    logger: logging.Logger | None = None,
) -> RetrainResult:
    """Load labels, build evidence, persist a fitted artifact and clear cache."""
    log = logger or logging.getLogger(__name__)
    with session_factory() as session:
        df = load_training_set(session)
    labelled = int(df["category"].notna().sum()) if not df.empty else 0
    log.info("Retrain: %d labelled rows", labelled)
    if labelled < MIN_RETRAIN_LABELLED_ROWS:
        message = f"Retrain aborted: too few labelled rows ({labelled})."
        log.warning(message)
        return RetrainResult(status="aborted", labelled_rows=labelled, message=message)

    report = build_evidence_report(df)
    log.info("Retrain CV report: %s", report.get("models", {}))
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / (
        f"classification_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pipe = fit_final(df, estimator, feature_set=feature_set)
    candidate_dir = model_path.parent / "candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = candidate_dir / (
        f"legacy_candidate_{estimator}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.joblib"
    )
    joblib.dump(
        build_model_artifact(
            estimator=estimator,
            feature_set=feature_set,
            pipeline=pipe,
            report=report,
        ),
        candidate_path,
    )
    log.info(
        "Retrain: unregistered candidate saved to %s; report saved to %s",
        candidate_path,
        report_path,
    )
    return RetrainResult(
        status="completed",
        labelled_rows=labelled,
        model_path=candidate_path,
        report_path=report_path,
    )
