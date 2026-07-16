"""Dashboard-oriented classifier status aggregations."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.models import MlModelVersion, MlTrainingJob
from finance.ml.classification.artifact_status import (
    empty_model_status,
    model_status_from_disk,
)
from finance.ml.classification.artifacts import artifact_sha256
from finance.ml.classification.constants import (
    MODEL_MIN_CLASS_SUPPORT,
    RETRAIN_FEEDBACK_EVENTS_THRESHOLD,
    RETRAIN_LABEL_GROWTH_THRESHOLD,
    RETRAIN_REJECTION_MIN_EVENTS,
    RETRAIN_REJECTION_RATE_THRESHOLD,
)
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.evaluation import build_label_readiness
from finance.ml.classification.lifecycle import (
    active_model_version,
    active_training_report,
    training_data_preflight,
)
from finance.ml.classification.status_comparison import as_float, recommend_model
from finance.ml.classification.status_io import parse_iso_datetime
from finance.ml.feedback import confusion_hotspots, feedback_quality, feedback_report


def readiness_summary(session: Session) -> dict[str, Any]:
    df = load_training_set(session)
    summary = dict(build_label_readiness(df))
    preflight = training_data_preflight(df)
    summary["model_min_class_support"] = MODEL_MIN_CLASS_SUPPORT
    summary["supported_classes"] = preflight["supported_classes"]
    summary["unsupported_classes"] = preflight["unsupported_classes"]
    summary["split_feasible"] = preflight["split_feasible"]
    summary["split_error"] = preflight["split_error"]
    summary["training_ready"] = bool(preflight["ready"]) and bool(
        summary["technical_ready"]
    )
    reasons = preflight["reason_codes"]
    reason_codes = (
        [str(reason) for reason in reasons] if isinstance(reasons, list) else []
    )
    if not summary["technical_ready"]:
        reason_codes.append("total_below_minimum")
    summary["training_preflight_reasons"] = reason_codes
    return summary


def _mean(values: list[object]) -> float | None:
    numeric = [number for value in values if (number := as_float(value)) is not None]
    return sum(numeric) / len(numeric) if numeric else None


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _latest_completed_training_job(session: Session) -> MlTrainingJob | None:
    return session.execute(
        select(MlTrainingJob)
        .where(MlTrainingJob.status == "completed")
        .order_by(MlTrainingJob.finished_at.desc(), MlTrainingJob.created_at.desc())
    ).scalars().first()


def latest_training_report_path(session: Session) -> Path | None:
    """Return the report belonging to the latest completed job, when available."""
    job = _latest_completed_training_job(session)
    if job is None or not job.report_path:
        return None
    path = Path(job.report_path)
    return path if path.exists() else None


def runtime_model_status(
    session: Session,
) -> dict[str, Any]:
    """Inspect only the artifact registered as active in the current database."""
    active = active_model_version(session)
    if active is None:
        return empty_model_status()

    active_path = Path(active.artifact_path)
    status = model_status_from_disk(model_path=active_path)
    checksum_matches = (
        active_path.exists()
        and artifact_sha256(active_path) == active.artifact_sha256
    )
    if status.get("model_version_id") != active.id or not checksum_matches:
        missing = empty_model_status()
        missing["path"] = str(active_path)
        missing["load_error"] = (
            "model_retrain_required: the active artifact is missing, changed or "
            "does not match the model registry."
        )
        return missing

    status["estimator"] = active.estimator
    status["feature_set"] = active.feature_set
    active_report = active_training_report(session)
    status["report_path"] = active_report["path"]
    status["report_updated_at"] = active_report["updated_at"]
    metrics = cast(dict[str, Any], active.metrics or {})
    time_metrics = _mapping(metrics.get("time"))
    merchant_metrics = _mapping(metrics.get("merchant"))
    ranking = _mapping(metrics.get("ranking"))
    status["best_model"] = {
        "model": active.estimator,
        "macro_f1": ranking.get("worst_macro_f1"),
        "weighted_f1": _mean(
            [time_metrics.get("weighted_f1"), merchant_metrics.get("weighted_f1")]
        ),
        "coverage_at_055": _mean(
            [time_metrics.get("coverage"), merchant_metrics.get("coverage")]
        ),
        "accuracy_at_055": _mean(
            [
                time_metrics.get("accuracy_on_covered"),
                merchant_metrics.get("accuracy_on_covered"),
            ]
        ),
    }
    if status.get("compatibility_warnings") and not status.get("load_error"):
        status["load_error"] = (
            "model_retrain_required: the active artifact is incompatible with "
            "the current locked runtime."
        )
    return status


def registered_model_comparison(session: Session) -> list[dict[str, Any]]:
    """Compare only candidates produced by the latest completed comparable job."""
    latest_job = _latest_completed_training_job(session)
    if latest_job is None:
        return []
    versions = list(
        session.execute(
            select(MlModelVersion)
            .where(MlModelVersion.job_id == latest_job.id)
            .where(MlModelVersion.dataset_fingerprint == latest_job.dataset_fingerprint)
            .where(
                MlModelVersion.evaluation_set_id.is_not_distinct_from(
                    latest_job.evaluation_set_id
                )
            )
            .order_by(MlModelVersion.created_at.desc())
        ).scalars()
    )
    rows: list[dict[str, Any]] = []
    for version in versions:
        metrics = cast(dict[str, Any], version.metrics or {})
        time_metrics = _mapping(metrics.get("time"))
        merchant_metrics = _mapping(metrics.get("merchant"))
        ranking = _mapping(metrics.get("ranking"))
        gates = cast(dict[str, Any], version.gates or {})
        rows.append(
            {
                "model_id": version.id,
                "estimator": version.estimator,
                "feature_set": version.feature_set,
                "rank": None,
                "macro_f1": ranking.get("mean_macro_f1"),
                "weighted_f1": _mean(
                    [time_metrics.get("weighted_f1"), merchant_metrics.get("weighted_f1")]
                ),
                "coverage_at_055": _mean(
                    [time_metrics.get("coverage"), merchant_metrics.get("coverage")]
                ),
                "accuracy_at_055": _mean(
                    [
                        time_metrics.get("accuracy_on_covered"),
                        merchant_metrics.get("accuracy_on_covered"),
                    ]
                ),
                "time_holdout_macro_f1": time_metrics.get("macro_f1"),
                "merchant_group_macro_f1": merchant_metrics.get("macro_f1"),
                "stability_score": ranking.get("worst_macro_f1"),
                "confidence_note": gates.get("level"),
                "skipped": not version.promotable,
                "error": None,
                "is_recommended": False,
                "is_current": version.status == "active",
            }
        )
    rows.sort(
        key=lambda row: (
            row["skipped"],
            -(float(row["stability_score"]) if row["stability_score"] is not None else -1.0),
            -(float(row["macro_f1"]) if row["macro_f1"] is not None else -1.0),
            str(row["feature_set"]),
            str(row["estimator"]),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def latest_training_summary(
    session: Session,
    *,
    job: MlTrainingJob | None,
    comparison: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build one coherent summary from the latest completed training job."""
    if job is None:
        return {"exists": False}

    representative = next(
        (row for row in comparison if row.get("is_recommended")),
        comparison[0] if comparison else None,
    )
    version = (
        session.get(MlModelVersion, str(representative["model_id"]))
        if representative is not None
        else None
    )
    metrics = _mapping(version.metrics if version is not None else None)
    class_counts = _mapping(metrics.get("class_counts"))
    label_count = sum(
        int(value)
        for value in class_counts.values()
        if isinstance(value, (int, float))
    )
    time_metrics = _mapping(metrics.get("time"))
    merchant_metrics = _mapping(metrics.get("merchant"))
    oof_metrics = _mapping(metrics.get("oof"))
    result = _mapping(job.result)
    raw_labels = metrics.get("labels")
    supported_classes = (
        [str(value) for value in raw_labels]
        if isinstance(raw_labels, list)
        else []
    )
    raw_failures = result.get("failed_variants")
    failed_variants = raw_failures if isinstance(raw_failures, list) else []
    report_path = Path(job.report_path) if job.report_path else None
    duration_seconds = None
    if job.started_at is not None and job.finished_at is not None:
        duration_seconds = max(
            (job.finished_at - job.started_at).total_seconds(),
            0.0,
        )

    return {
        "exists": True,
        "job_id": job.id,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "duration_seconds": duration_seconds,
        "dataset_fingerprint": job.dataset_fingerprint,
        "evaluation_set_id": job.evaluation_set_id,
        "report_available": bool(report_path and report_path.exists()),
        "candidate_count": len(comparison),
        "recommended_model_id": result.get("recommended_model_id"),
        "representative_model_id": version.id if version is not None else None,
        "label_count": label_count or None,
        "supported_classes": supported_classes,
        "unsupported_classes": _mapping(metrics.get("unsupported_classes")),
        "split_counts": {
            "train": oof_metrics.get("n"),
            "time": time_metrics.get("n"),
            "merchant": merchant_metrics.get("n"),
        },
        "metrics": metrics,
        "gates": _mapping(version.gates if version is not None else None),
        "confidence_policy": _mapping(
            version.confidence_policy if version is not None else None
        ),
        "failed_variants": failed_variants,
    }


def retrain_signal(
    session: Session,
    status: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    model_updated_at = parse_iso_datetime(status.get("updated_at"))
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
) -> dict[str, Any]:
    status = runtime_model_status(session)
    readiness = readiness_summary(session)
    status["retrain_signal"] = retrain_signal(session, status, readiness)
    comparison = registered_model_comparison(session)
    return {
        "models": comparison,
        "recommendation": recommend_model(comparison, status, readiness),
    }


def dashboard_summary(
    session: Session,
) -> dict[str, Any]:
    status = runtime_model_status(session)
    readiness = readiness_summary(session)
    signal = retrain_signal(session, status, readiness)
    status["retrain_signal"] = signal
    latest = active_training_report(session)
    latest_job = _latest_completed_training_job(session)
    comparison = registered_model_comparison(session)
    recommendation = recommend_model(comparison, status, readiness)
    latest_training = latest_training_summary(
        session,
        job=latest_job,
        comparison=comparison,
    )
    feedback_since = latest_job.finished_at if latest_job is not None else None
    scoped_feedback = feedback_quality(session, since=feedback_since)
    scoped_feedback["scope"] = (
        "since_last_training" if feedback_since is not None else "all_time"
    )
    scoped_feedback["period_start"] = (
        feedback_since.isoformat() if feedback_since is not None else None
    )
    active = active_model_version(session)
    active_metrics = cast(dict[str, Any], active.metrics or {}) if active else {}
    return {
        "status": status,
        "readiness": readiness,
        "latest_report": latest,
        "latest_training": latest_training,
        "model_comparison": comparison,
        "recommendation": recommendation,
        "validation_slices": {
            key: active_metrics[key]
            for key in ("time", "merchant")
            if key in active_metrics
        },
        "confidence_policy": dict(active.confidence_policy or {}) if active else {},
        "feedback_quality": scoped_feedback,
        "feedback_report": feedback_report(
            session,
            model_updated_at=parse_iso_datetime(status.get("updated_at")),
            labels_used_in_current_model=status.get("n_total_labelled"),
            current_label_count=readiness.get("total_labelled"),
        ),
        "retrain_signal": signal,
        "confusion_hotspots": confusion_hotspots(session, since=feedback_since),
    }
