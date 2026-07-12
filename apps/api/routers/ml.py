"""POST /ml/classify  — classify a single transaction-like payload.
POST /ml/reclassify — bulk-predict for rows without a ground-truth category.
POST /ml/retrain    — refit the classifier on current DB labels (background).
"""
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib  # noqa: F401 - tests use apps.api.routers.ml.joblib for artifacts.
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.errors import bad_request, conflict, not_found, service_unavailable
from apps.api.schemas.ml import (
    ClassificationDecisionResponse,
    ClassifyRequest,
    ClassifyResponse,
    FeedbackReportResponse,
    MlComparisonResponse,
    MlDashboardResponse,
    MlEvaluationSetResponse,
    MlFeedbackRequest,
    MlFeedbackResponse,
    MlLatestReportResponse,
    MlModelStatus,
    MlModelVersionResponse,
    MlReadinessResponse,
    ReclassifyResponse,
    RetrainResponse,
    RetrainStatusResponse,
    ReviewQueueItemResponse,
)
from finance.db import SessionLocal, get_session
from finance.ml.classification.evaluation_sets import (
    EvaluationSetError,
    evaluation_set_summary,
    freeze_evaluation_set,
)
from finance.ml.classification.lifecycle import (
    ModelActivationError,
    TrainingJobConflict,
    activate_model_version,
    active_training_report,
    enqueue_training_job,
    model_versions,
    run_training_job,
    training_job,
)
from finance.ml.classification.policy import ClassificationPolicy
from finance.ml.classification.predict import (
    ClassifierNotAvailable,
    active_classification_policy,
    predict_transaction,
    reclassify_unlabelled,
    require_registered_active_artifact,
)
from finance.ml.classification.status import (
    MODEL_PATH as DEFAULT_MODEL_PATH,
)
from finance.ml.classification.status import (
    REPORTS_DIR as DEFAULT_REPORTS_DIR,
)
from finance.ml.classification.status import (
    comparison_summary,
    dashboard_summary,
    readiness_summary,
    retrain_signal,
    runtime_model_status,
)
from finance.ml.feedback import (
    FeedbackEventInput,
    feedback_report,
    record_feedback_event,
)
from finance.ml.review_queue import review_queue
from finance.transactions.type_reclassification import reclassify_transaction_types

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])

MODEL_PATH: Path = DEFAULT_MODEL_PATH
REPORTS_DIR: Path = DEFAULT_REPORTS_DIR


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _classification_policy(session: Session) -> ClassificationPolicy:
    return active_classification_policy(session=session)


@router.get("/status", response_model=MlModelStatus)
def model_status(session: Session = Depends(get_session)) -> MlModelStatus:
    status = runtime_model_status(
        session,
        model_path=MODEL_PATH,
        reports_dir=REPORTS_DIR,
    )
    readiness_data = readiness_summary(session)
    status["retrain_signal"] = retrain_signal(session, status, readiness_data)
    return MlModelStatus(**status)


@router.get("/readiness", response_model=MlReadinessResponse)
def readiness(session: Session = Depends(get_session)) -> MlReadinessResponse:
    return MlReadinessResponse(**readiness_summary(session))


@router.get("/report/latest", response_model=MlLatestReportResponse)
def latest_report(
    session: Session = Depends(get_session),
) -> MlLatestReportResponse:
    report = active_training_report(session)
    payload = report.get("report")
    return MlLatestReportResponse(
        path=str(report["path"]) if report.get("path") else None,
        updated_at=str(report["updated_at"]) if report.get("updated_at") else None,
        report=payload if isinstance(payload, dict) else None,
    )


@router.get("/report/latest/file")
def latest_report_file(
    download: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> FileResponse:
    report = active_training_report(session)
    path_value = report.get("path")
    if not path_value:
        raise not_found("No report belongs to an active registered model.")
    path = Path(str(path_value))
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/comparison", response_model=MlComparisonResponse)
def model_comparison(
    session: Session = Depends(get_session),
) -> MlComparisonResponse:
    return MlComparisonResponse(
        **comparison_summary(session, model_path=MODEL_PATH, reports_dir=REPORTS_DIR)
    )


@router.get("/dashboard", response_model=MlDashboardResponse)
def dashboard(session: Session = Depends(get_session)) -> MlDashboardResponse:
    return MlDashboardResponse(
        **dashboard_summary(session, model_path=MODEL_PATH, reports_dir=REPORTS_DIR)
    )


@router.get("/review-queue", response_model=list[ReviewQueueItemResponse])
def review_queue_endpoint(
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ReviewQueueItemResponse]:
    policy = _classification_policy(session)
    rows = review_queue(session, limit=limit, policy=policy)
    return [ReviewQueueItemResponse(**row.__dict__) for row in rows]


@router.get("/feedback-report", response_model=FeedbackReportResponse)
def feedback_report_endpoint(
    session: Session = Depends(get_session),
) -> FeedbackReportResponse:
    status = runtime_model_status(
        session,
        model_path=MODEL_PATH,
        reports_dir=REPORTS_DIR,
    )
    readiness_data = readiness_summary(session)
    updated_at = status.get("updated_at")
    try:
        model_updated_at = (
            datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
            if updated_at
            else None
        )
    except ValueError:
        model_updated_at = None
    report = feedback_report(
        session,
        model_updated_at=model_updated_at,
        labels_used_in_current_model=status.get("n_total_labelled"),
        current_label_count=readiness_data.get("total_labelled"),
    )
    return FeedbackReportResponse(**report)


@router.post("/classify", response_model=ClassifyResponse)
def classify(
    req: ClassifyRequest,
    session: Session = Depends(get_session),
) -> ClassifyResponse:
    try:
        artifact = require_registered_active_artifact(session)
        policy = active_classification_policy(
            artifact=artifact,
            fallback=ClassificationPolicy(default_threshold=req.threshold),
        )
        result = predict_transaction(
            req.merchant,
            req.title,
            req.amount,
            req.booking_date,
            threshold=req.threshold,
            use_llm_fallback=req.use_llm_fallback,
            source=req.source,
            transaction_type=req.transaction_type.value,
            direction=req.direction.value if req.direction is not None else None,
            is_transfer=req.is_transfer,
            policy=policy,
            artifact=artifact if artifact else None,
        )
    except ClassifierNotAvailable as exc:
        raise service_unavailable(
            {"code": "model_retrain_required", "message": str(exc)}
        ) from exc
    return ClassifyResponse(
        category=result.category,
        confidence=result.confidence,
        model_confidence=result.model_confidence,
        source=result.source,
        model_category=result.model_category,
        threshold=result.threshold,
        threshold_used=result.threshold,
        fallback_used=result.fallback_used,
        top_predictions=result.top_predictions,
        recommended_action=result.recommended_action,
        classification_decision=ClassificationDecisionResponse(
            **result.classification_decision.__dict__,
        ),
    )


@router.post("/feedback", response_model=MlFeedbackResponse)
def record_feedback(
    req: MlFeedbackRequest,
    session: Session = Depends(get_session),
) -> MlFeedbackResponse:
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            transaction_id=req.transaction_id,
            entity_type=req.entity_type,
            entity_key=req.entity_key,
            event_type=req.event_type,
            predicted_category=req.predicted_category,
            final_category=req.final_category,
            confidence=req.confidence,
            source=req.source,
            model_artifact=req.model_artifact,
        ),
    )
    session.commit()
    session.refresh(event)
    return MlFeedbackResponse(id=event.id)


@router.post("/reclassify", response_model=ReclassifyResponse)
def reclassify(session: Session = Depends(get_session)) -> ReclassifyResponse:
    policy = active_classification_policy(session=session)
    try:
        n = reclassify_unlabelled(session, policy=policy)
    except ClassifierNotAvailable as exc:
        raise service_unavailable(
            {"code": "model_retrain_required", "message": str(exc)}
        ) from exc
    return ReclassifyResponse(updated=n)


@router.post("/transaction-types/reclassify", response_model=ReclassifyResponse)
def reclassify_types(session: Session = Depends(get_session)) -> ReclassifyResponse:
    """Recalculate only non-confirmed transaction-type decisions."""
    return ReclassifyResponse(updated=reclassify_transaction_types(session))


def _retrain_job(job_id: str) -> None:
    run_training_job(session_factory=SessionLocal, job_id=job_id, logger=logger)


@router.get("/retrain/status", response_model=RetrainStatusResponse)
def retrain_status(
    job_id: str | None = None,
    session: Session = Depends(get_session),
) -> RetrainStatusResponse:
    job = training_job(session, job_id)
    if job is None:
        return RetrainStatusResponse(status="idle", message="No training job exists.")
    return RetrainStatusResponse(
        job_id=job.id,
        status=job.status,
        message=job.message,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        report_path=job.report_path,
        result=dict(job.result or {}),
        error=job.error,
    )


@router.post("/retrain", response_model=RetrainResponse, status_code=202)
def retrain(
    background: BackgroundTasks,
    estimator: str | None = None,
    feature_set: str | None = None,
    include_benchmarks: bool = False,
    session: Session = Depends(get_session),
) -> RetrainResponse:
    readiness_data = readiness_summary(session)
    if not bool(readiness_data.get("training_ready")):
        raise conflict(
            {
                "code": "training_data_not_ready",
                "message": (
                    "Training requires confirmed labels with enough support "
                    "for deterministic validation."
                ),
                "readiness": readiness_data,
            }
        )
    try:
        job = enqueue_training_job(
            session,
            estimator=estimator,
            feature_set=feature_set,
            include_benchmarks=include_benchmarks,
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except TrainingJobConflict as exc:
        raise conflict(str(exc)) from exc
    background.add_task(_retrain_job, job.id)
    return RetrainResponse(
        status="scheduled",
        message="Candidate evaluation queued; manual activation will be required.",
        job_id=job.id,
    )


def _model_version_response(row: Any) -> MlModelVersionResponse:
    return MlModelVersionResponse(
        id=row.id,
        job_id=row.job_id,
        estimator=row.estimator,
        feature_set=row.feature_set,
        status=row.status,
        artifact_sha256=row.artifact_sha256,
        dataset_fingerprint=row.dataset_fingerprint,
        evaluation_set_id=row.evaluation_set_id,
        metrics=dict(row.metrics or {}),
        gates=dict(row.gates or {}),
        promotable=row.promotable,
        created_at=row.created_at.isoformat(),
        activated_at=row.activated_at.isoformat() if row.activated_at else None,
    )


@router.get("/model-versions", response_model=list[MlModelVersionResponse])
def list_model_versions(
    session: Session = Depends(get_session),
) -> list[MlModelVersionResponse]:
    return [_model_version_response(row) for row in model_versions(session)]


@router.post("/model-versions/{model_id}/activate", response_model=MlModelVersionResponse)
def activate_model(
    model_id: str,
    session: Session = Depends(get_session),
) -> MlModelVersionResponse:
    version = next((row for row in model_versions(session) if row.id == model_id), None)
    if version is None:
        raise not_found("Category model version not found")
    try:
        row = activate_model_version(session, model_id)
    except ModelActivationError as exc:
        raise conflict(str(exc)) from exc
    return _model_version_response(row)


@router.get("/evaluation-sets/current", response_model=MlEvaluationSetResponse)
def current_evaluation_set_endpoint(
    session: Session = Depends(get_session),
) -> MlEvaluationSetResponse:
    return MlEvaluationSetResponse.model_validate(evaluation_set_summary(session))


@router.post("/evaluation-sets/freeze", response_model=MlEvaluationSetResponse)
def freeze_evaluation_set_endpoint(
    session: Session = Depends(get_session),
) -> MlEvaluationSetResponse:
    try:
        freeze_evaluation_set(session)
    except EvaluationSetError as exc:
        raise conflict(str(exc)) from exc
    return MlEvaluationSetResponse.model_validate(evaluation_set_summary(session))
