"""Durable candidate training, activation and rollback services."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance.domain.models import MlModelVersion, MlTrainingJob
from finance.ml.classification.artifacts import (
    artifact_sha256,
    build_model_artifact,
    require_compatible_artifact,
)
from finance.ml.classification.candidate_evaluation import (
    ALL_LABELS,
    CandidateEvaluation,
    candidate_variants,
    development_split_ids,
    evaluate_benchmark,
    evaluate_candidate,
    evaluate_pipeline_slices,
    full_matrix_variants,
    prepare_experiment,
    rank_evaluations,
)
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.evaluation_sets import (
    current_evaluation_set,
    dataset_fingerprint,
    split_transaction_ids,
)
from finance.ml.classification.predict import load_registered_artifact

CANDIDATES_DIR = Path("data/models/candidates")
REPORTS_DIR = Path("data/reports")
EXECUTION_SLOT = 1


class TrainingJobConflict(RuntimeError):
    """Raised when the single local training slot is occupied."""


class ModelActivationError(RuntimeError):
    """Raised when a model version cannot safely become active."""


def training_data_preflight(df: pd.DataFrame) -> dict[str, object]:
    """Check whether the fixed matrix can produce leakage-free CV and holdouts."""
    counts = (
        df["category"].astype(str).value_counts().to_dict() if not df.empty else {}
    )
    category_counts = {label: int(counts.get(label, 0)) for label in ALL_LABELS}
    reasons: list[str] = []
    if df.empty:
        reasons.append("no_confirmed_labels")
    missing = [label for label, count in category_counts.items() if count == 0]
    if missing:
        reasons.append("missing_categories")
    if not reasons:
        try:
            prepare_experiment(df)
        except ValueError:
            reasons.append("holdouts_not_feasible")
    return {
        "ready": not reasons,
        "total": int(len(df)),
        "category_counts": category_counts,
        "reason_codes": reasons,
    }


def enqueue_training_job(
    session: Session,
    *,
    estimator: str | None = None,
    feature_set: str | None = None,
    include_benchmarks: bool = False,
) -> MlTrainingJob:
    if include_benchmarks:
        if estimator is not None or feature_set is not None:
            raise ValueError(
                "Research benchmark mode cannot be combined with candidate filters."
            )
        variants = full_matrix_variants()
    else:
        variants = [
            (variant_estimator, variant_features, True)
            for variant_estimator, variant_features in candidate_variants(
                estimator,
                feature_set,
            )
        ]
    job = MlTrainingJob(
        id=str(uuid4()),
        status="queued",
        execution_slot=EXECUTION_SLOT,
        requested_variants=[
            {
                "estimator": estimator_name,
                "feature_set": features,
                "promotable": promotable,
            }
            for estimator_name, features, promotable in variants
        ],
        result={},
        message="Training job queued.",
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise TrainingJobConflict("A training job is already queued or running.") from exc
    session.refresh(job)
    return job


def mark_interrupted_jobs(session: Session) -> int:
    jobs = list(
        session.execute(
            select(MlTrainingJob).where(MlTrainingJob.status.in_(["queued", "running"]))
        ).scalars()
    )
    now = datetime.now(UTC)
    for job in jobs:
        job.status = "interrupted"
        job.execution_slot = None
        job.finished_at = now
        job.message = "API restarted while the local training job was running."
    session.commit()
    return len(jobs)


def _active_comparison(
    session: Session,
    *,
    df: pd.DataFrame,
    split_ids: dict[str, set[int]],
    evaluation_set_id: str | None,
) -> dict[str, object] | None:
    active = session.execute(
        select(MlModelVersion)
        .where(MlModelVersion.status == "active")
        .order_by(MlModelVersion.activated_at.desc())
    ).scalars().first()
    if active is None:
        return None
    if active.evaluation_set_id != evaluation_set_id:
        return None
    try:
        artifact = load_registered_artifact(
            str(active.artifact_path),
            active.artifact_sha256,
            active.id,
        )
        pipeline = artifact.get("pipeline")
        if pipeline is None:
            raise ValueError("Active artifact does not contain a pipeline.")
        policy = artifact.get("confidence_policy")
        confidence_policy = (
            policy if isinstance(policy, dict) else dict(active.confidence_policy or {})
        )
        return evaluate_pipeline_slices(
            df,
            pipeline=pipeline,
            feature_set=active.feature_set,
            split_ids=split_ids,
            confidence_policy=confidence_policy,
        )
    except Exception as exc:
        raise ValueError(
            "The active model cannot be evaluated as the regression baseline."
        ) from exc


def _artifact_sha256(path: Path) -> str:
    """Backward-compatible internal alias used by existing callers and tests."""
    return artifact_sha256(path)


def _serializable_result(result: CandidateEvaluation) -> dict[str, object]:
    return {
        "estimator": result.estimator,
        "feature_set": result.feature_set,
        "metrics": result.metrics,
        "confidence_policy": result.confidence_policy,
        "gates": result.gates,
    }


def _write_candidate_artifact(
    result: CandidateEvaluation,
    *,
    model_id: str,
    fingerprint: str,
    evaluation_set_id: str | None,
    n_total_labelled: int,
) -> tuple[Path, str]:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    final_path = CANDIDATES_DIR / f"{model_id}.joblib"
    temporary_path = CANDIDATES_DIR / f".{model_id}.tmp.joblib"
    report = _serializable_result(result) | {
        "labels": ALL_LABELS,
        "n_classes": len(ALL_LABELS),
        "n_total_labelled": n_total_labelled,
    }
    artifact = build_model_artifact(
        estimator=result.estimator,
        feature_set=result.feature_set,
        pipeline=result.pipeline,
        report=report,
        model_version_id=model_id,
        dataset_fingerprint=fingerprint,
        evaluation_set_id=evaluation_set_id,
        confidence_policy=result.confidence_policy,
    )
    joblib.dump(artifact, temporary_path)
    temporary_path.replace(final_path)
    return final_path, _artifact_sha256(final_path)


def _finish_failed_job(
    session_factory: Callable[[], Session],
    job_id: str,
    exc: Exception,
    log: logging.Logger,
) -> None:
    log.exception("Classifier candidate training failed", exc_info=exc)
    with session_factory() as session:
        job = session.get(MlTrainingJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.execution_slot = None
        job.finished_at = datetime.now(UTC)
        job.message = "Training job failed."
        job.error = str(exc)
        session.commit()


def run_training_job(
    *,
    session_factory: Callable[[], Session],
    job_id: str,
    logger: Any | None = None,
) -> None:
    """Execute one previously queued job and register candidates, never activate them."""
    log = logger or logging.getLogger(__name__)
    try:
        with session_factory() as session:
            job = session.get(MlTrainingJob, job_id)
            if job is None or job.status != "queued":
                return
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.message = "Evaluating classifier candidates."
            session.commit()

        with session_factory() as session:
            job = session.get(MlTrainingJob, job_id)
            if job is None:
                return
            df = load_training_set(session)
            if df.empty:
                raise ValueError("No explicitly confirmed category labels are available.")
            fingerprint = dataset_fingerprint(df)
            evaluation_set = current_evaluation_set(session)
            evaluation_set_id = evaluation_set.id if evaluation_set else None
            split_ids = (
                split_transaction_ids(session, evaluation_set.id)
                if evaluation_set
                else development_split_ids(df)
            )
            active_metrics = _active_comparison(
                session,
                df=df,
                split_ids=split_ids,
                evaluation_set_id=evaluation_set_id,
            )
            requested = list(job.requested_variants or [])

        evaluations: list[CandidateEvaluation] = []
        benchmarks: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for variant in requested:
            estimator = str(variant["estimator"])
            feature_set = str(variant["feature_set"])
            try:
                if bool(variant.get("promotable", True)):
                    evaluations.append(
                        evaluate_candidate(
                            df,
                            estimator=estimator,
                            feature_set=feature_set,
                            split_ids=split_ids,
                            frozen_evaluation_set=evaluation_set_id is not None,
                            active_metrics=active_metrics,
                        )
                    )
                else:
                    benchmarks.append(
                        evaluate_benchmark(
                            df,
                            estimator=estimator,
                            feature_set=feature_set,
                            split_ids=split_ids,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "estimator": estimator,
                        "feature_set": feature_set,
                        "error": str(exc),
                    }
                )

        ranked = rank_evaluations(evaluations)
        if not ranked:
            raise ValueError(f"All candidate variants failed: {failures}")

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        finished_at = datetime.now(UTC)
        report_path = REPORTS_DIR / f"classification_job_{job_id}.json"
        model_rows: list[MlModelVersion] = []
        summaries: list[dict[str, object]] = []
        for rank, result in enumerate(ranked, start=1):
            model_id = str(uuid4())
            artifact_path, artifact_sha = _write_candidate_artifact(
                result,
                model_id=model_id,
                fingerprint=fingerprint,
                evaluation_set_id=evaluation_set_id,
                n_total_labelled=len(df),
            )
            summary = _serializable_result(result) | {
                "id": model_id,
                "rank": rank,
                "artifact_sha256": artifact_sha,
            }
            summaries.append(summary)
            model_rows.append(
                MlModelVersion(
                    id=model_id,
                    job_id=job_id,
                    estimator=result.estimator,
                    feature_set=result.feature_set,
                    status="candidate" if result.gates["promotable"] else "rejected",
                    artifact_path=str(artifact_path),
                    artifact_sha256=artifact_sha,
                    dataset_fingerprint=fingerprint,
                    evaluation_set_id=evaluation_set_id,
                    metrics=result.metrics,
                    gates=result.gates,
                    confidence_policy=result.confidence_policy,
                    promotable=bool(result.gates["promotable"]),
                )
            )
        report = {
            "report_type": "classification_candidate_job",
            "job_id": job_id,
            "created_at": finished_at.isoformat(),
            "dataset_fingerprint": fingerprint,
            "evaluation_set_id": evaluation_set_id,
            "split_counts": {key: len(value) for key, value in split_ids.items()},
            "recommended_model_id": model_rows[0].id,
            "candidates": summaries,
            "benchmarks": benchmarks,
            "failed_variants": failures,
            "privacy_note": "Aggregate metrics only; no raw merchant or title values.",
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )

        with session_factory() as session:
            job = session.get(MlTrainingJob, job_id)
            if job is None:
                return
            session.add_all(model_rows)
            job.status = "completed"
            job.execution_slot = None
            job.dataset_fingerprint = fingerprint
            job.evaluation_set_id = evaluation_set_id
            job.report_path = str(report_path)
            job.result = {
                "recommended_model_id": model_rows[0].id,
                "candidate_ids": [row.id for row in model_rows],
                "failed_variants": failures,
            }
            job.message = "Candidate evaluation completed; manual activation is required."
            job.finished_at = finished_at
            session.commit()
    except Exception as exc:  # noqa: BLE001
        _finish_failed_job(session_factory, job_id, exc, log)


def _smoke_test_artifact(artifact: dict[str, object]) -> None:
    pipeline: Any = artifact.get("pipeline")
    if pipeline is None or not hasattr(pipeline, "predict_proba"):
        raise ModelActivationError("Candidate does not expose calibrated predict_proba.")
    sample = pd.DataFrame(
        [
            {
                "text": "test merchant test transaction",
                "merchant": "test merchant",
                "title": "test transaction",
                "abs_amount": 10.0,
                "day_of_week": 0,
                "booking_date": datetime(2026, 1, 1).date(),
                "source": "unknown",
                "direction": "debit",
                "transaction_type": "expense",
            }
        ]
    )
    prediction = pipeline.predict(sample)
    probabilities = pipeline.predict_proba(sample)
    if len(prediction) != 1 or len(probabilities) != 1:
        raise ModelActivationError("Candidate smoke prediction returned an invalid shape.")


def activate_model_version(session: Session, model_id: str) -> MlModelVersion:
    version = session.get(MlModelVersion, model_id)
    if version is None:
        raise ModelActivationError("Model version does not exist.")
    if not version.promotable:
        raise ModelActivationError("Model version did not pass the technical gates.")
    path = Path(version.artifact_path)
    if not path.exists() or _artifact_sha256(path) != version.artifact_sha256:
        raise ModelActivationError("Candidate artifact checksum mismatch.")
    try:
        artifact = joblib.load(path)
        require_compatible_artifact(artifact)
        if artifact.get("task", "category") != "category":
            raise ModelActivationError("Candidate artifact is not a category model.")
        _smoke_test_artifact(artifact)
    except ModelActivationError:
        raise
    except Exception as exc:
        raise ModelActivationError("Candidate artifact failed compatibility checks.") from exc

    now = datetime.now(UTC)
    active_versions = list(
        session.execute(
            select(MlModelVersion).where(MlModelVersion.status == "active")
        ).scalars()
    )
    for active in active_versions:
        if active.id != version.id:
            active.status = "archived"
    session.flush()
    version.status = "active"
    version.activated_at = now
    session.commit()
    session.refresh(version)
    load_registered_artifact.cache_clear()
    return version


def model_versions(
    session: Session,
) -> list[MlModelVersion]:
    stmt = select(MlModelVersion)
    return list(
        session.execute(
            stmt.order_by(MlModelVersion.created_at.desc())
        ).scalars()
    )


def active_model_version(
    session: Session,
) -> MlModelVersion | None:
    return session.execute(
        select(MlModelVersion)
        .where(MlModelVersion.status == "active")
        .order_by(MlModelVersion.activated_at.desc())
    ).scalars().first()


def active_training_report(session: Session) -> dict[str, object]:
    """Return active metrics from the registry and an optional evidence-file path."""
    active = active_model_version(session)
    if active is None:
        return {"path": None, "updated_at": None, "report": None}
    job = session.get(MlTrainingJob, active.job_id) if active.job_id else None
    path = Path(job.report_path) if job and job.report_path else None
    available_path = str(path) if path is not None and path.exists() else None
    return {
        "path": available_path,
        "updated_at": active.created_at.isoformat(),
        "report": {
            "model_version_id": active.id,
            "job_id": active.job_id,
            "estimator": active.estimator,
            "feature_set": active.feature_set,
            "dataset_fingerprint": active.dataset_fingerprint,
            "evaluation_set_id": active.evaluation_set_id,
            "metrics": dict(active.metrics or {}),
            "gates": dict(active.gates or {}),
            "confidence_policy": dict(active.confidence_policy or {}),
        },
    }


def training_job(session: Session, job_id: str | None = None) -> MlTrainingJob | None:
    if job_id:
        return session.get(MlTrainingJob, job_id)
    return session.execute(
        select(MlTrainingJob).order_by(MlTrainingJob.created_at.desc())
    ).scalars().first()
