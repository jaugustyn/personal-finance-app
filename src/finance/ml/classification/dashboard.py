"""Dashboard-oriented classifier status aggregations."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from finance.ml.classification.artifact_status import model_status_from_disk
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
from finance.ml.classification.status_comparison import model_comparison, recommend_model
from finance.ml.classification.status_io import load_latest_report, parse_iso_datetime
from finance.ml.feedback import confusion_hotspots, feedback_quality, feedback_report


def readiness_summary(session: Session) -> dict[str, Any]:
    df = load_training_set(session)
    return dict(build_label_readiness(df))


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
            model_updated_at=parse_iso_datetime(status.get("updated_at")),
            labels_used_in_current_model=status.get("n_total_labelled"),
            current_label_count=readiness.get("total_labelled"),
        ),
        "retrain_signal": signal,
        "confusion_hotspots": confusion_hotspots(session),
    }
