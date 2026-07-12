"""Dashboard-oriented classifier status aggregations."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.models import MlModelVersion
from finance.ml.classification.artifact_status import (
    empty_model_status,
    model_status_from_disk,
)
from finance.ml.classification.artifacts import artifact_sha256
from finance.ml.classification.constants import (
    MODEL_PATH,
    REPORTS_DIR,
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


def runtime_model_status(
    session: Session,
    *,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    """Inspect only the artifact registered as active in the current database."""
    del reports_dir  # Reports are evidence outputs, not runtime state.
    active = active_model_version(session)
    if active is None:
        return empty_model_status(model_path=model_path)

    active_path = Path(active.artifact_path)
    status = model_status_from_disk(model_path=active_path)
    checksum_matches = (
        active_path.exists()
        and artifact_sha256(active_path) == active.artifact_sha256
    )
    if status.get("model_version_id") != active.id or not checksum_matches:
        missing = empty_model_status(model_path=active_path)
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
    """Build dashboard rows only from candidates registered in the current DB."""
    versions = list(
        session.execute(
            select(MlModelVersion)
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
                "merchant_group_holdout_macro_f1": merchant_metrics.get("macro_f1"),
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
    *,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    status = runtime_model_status(
        session,
        model_path=model_path,
        reports_dir=reports_dir,
    )
    readiness = readiness_summary(session)
    status["retrain_signal"] = retrain_signal(session, status, readiness)
    comparison = registered_model_comparison(session)
    return {
        "models": comparison,
        "recommendation": recommend_model(None, comparison, status, readiness),
    }


def dashboard_summary(
    session: Session,
    *,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    status = runtime_model_status(
        session,
        model_path=model_path,
        reports_dir=reports_dir,
    )
    readiness = readiness_summary(session)
    signal = retrain_signal(session, status, readiness)
    status["retrain_signal"] = signal
    latest = active_training_report(session)
    comparison = registered_model_comparison(session)
    active = active_model_version(session)
    active_metrics = cast(dict[str, Any], active.metrics or {}) if active else {}
    return {
        "status": status,
        "readiness": readiness,
        "latest_report": latest,
        "model_comparison": comparison,
        "recommendation": recommend_model(None, comparison, status, readiness),
        "validation_slices": {
            key: active_metrics[key]
            for key in ("time", "merchant")
            if key in active_metrics
        },
        "confidence_policy": dict(active.confidence_policy or {}) if active else {},
        "feedback_quality": feedback_quality(session),
        "feedback_report": feedback_report(
            session,
            model_updated_at=parse_iso_datetime(status.get("updated_at")),
            labels_used_in_current_model=status.get("n_total_labelled"),
            current_label_count=readiness.get("total_labelled"),
        ),
        "retrain_signal": signal,
        "confusion_hotspots": confusion_hotspots(session),
    }
