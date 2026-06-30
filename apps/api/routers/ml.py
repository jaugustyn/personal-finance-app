"""POST /ml/classify  — classify a single transaction-like payload.
POST /ml/reclassify — bulk-predict for rows without a ground-truth category.
POST /ml/retrain    — refit the classifier on current DB labels (background).
"""
import logging
from datetime import datetime
from pathlib import Path

import joblib  # noqa: F401 - tests use apps.api.routers.ml.joblib for artifacts.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.schemas.ml import (
    ClassificationDecisionResponse,
    ClassifyRequest,
    ClassifyResponse,
    FeedbackReportResponse,
    MlComparisonResponse,
    MlDashboardResponse,
    MlFeedbackRequest,
    MlFeedbackResponse,
    MlLatestReportResponse,
    MlModelStatus,
    MlReadinessResponse,
    ReclassifyResponse,
    RetrainResponse,
    ReviewQueueItemResponse,
)
from finance.db import SessionLocal, get_session
from finance.ml.classification.policy import (
    ClassificationPolicy,
    policy_from_report,
)
from finance.ml.classification.predict import (
    ClassifierNotAvailable,
    predict_transaction,
    reclassify_unlabelled,
)
from finance.ml.classification.registry import ESTIMATORS
from finance.ml.classification.retrain import retrain_classifier
from finance.ml.classification.status import (
    DEFAULT_RECOMMENDED_ESTIMATOR,
    DEFAULT_RECOMMENDED_FEATURE_SET,
    comparison_summary,
    dashboard_summary,
    load_latest_report,
    model_status_from_disk,
    readiness_summary,
    retrain_signal,
)
from finance.ml.classification.status import (
    MODEL_PATH as DEFAULT_MODEL_PATH,
)
from finance.ml.classification.status import (
    REPORTS_DIR as DEFAULT_REPORTS_DIR,
)
from finance.ml.feedback import (
    FeedbackEventInput,
    feedback_report,
    record_feedback_event,
)
from finance.ml.review_queue import review_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])

MODEL_PATH: Path = DEFAULT_MODEL_PATH
REPORTS_DIR: Path = DEFAULT_REPORTS_DIR


def _classification_policy() -> ClassificationPolicy:
    latest = load_latest_report(REPORTS_DIR)
    report = latest["report"] if isinstance(latest["report"], dict) else None
    return policy_from_report(report)


@router.get("/status", response_model=MlModelStatus)
def model_status(session: Session = Depends(get_session)) -> MlModelStatus:
    status = model_status_from_disk(model_path=MODEL_PATH, reports_dir=REPORTS_DIR)
    readiness_data = readiness_summary(session)
    status["retrain_signal"] = retrain_signal(session, status, readiness_data)
    return MlModelStatus(**status)


@router.get("/readiness", response_model=MlReadinessResponse)
def readiness(session: Session = Depends(get_session)) -> MlReadinessResponse:
    return MlReadinessResponse(**readiness_summary(session))


@router.get("/report/latest", response_model=MlLatestReportResponse)
def latest_report() -> MlLatestReportResponse:
    return MlLatestReportResponse(**load_latest_report(REPORTS_DIR))


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
    policy = _classification_policy()
    rows = review_queue(session, limit=limit, policy=policy)
    return [ReviewQueueItemResponse(**row.__dict__) for row in rows]


@router.get("/feedback-report", response_model=FeedbackReportResponse)
def feedback_report_endpoint(
    session: Session = Depends(get_session),
) -> FeedbackReportResponse:
    status = model_status_from_disk(model_path=MODEL_PATH, reports_dir=REPORTS_DIR)
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
def classify(req: ClassifyRequest) -> ClassifyResponse:
    latest = load_latest_report(REPORTS_DIR)
    report = latest["report"] if isinstance(latest["report"], dict) else None
    policy = policy_from_report(
        report,
        fallback=ClassificationPolicy(default_threshold=req.threshold),
    )
    try:
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
        )
    except ClassifierNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ClassifyResponse(
        category=result.category,
        confidence=result.confidence,
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
    latest = load_latest_report(REPORTS_DIR)
    report = latest["report"] if isinstance(latest["report"], dict) else None
    policy = policy_from_report(report)
    try:
        n = reclassify_unlabelled(session, policy=policy)
    except ClassifierNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReclassifyResponse(updated=n)


def _retrain_job(
    estimator: str,
    feature_set: str = DEFAULT_RECOMMENDED_FEATURE_SET,
) -> None:
    """Background wrapper around the classifier retraining use case."""
    try:
        retrain_classifier(
            session_factory=SessionLocal,
            estimator=estimator,
            feature_set=feature_set,
            model_path=MODEL_PATH,
            reports_dir=REPORTS_DIR,
            logger=logger,
        )
    except Exception:
        logger.exception("Retrain job failed")


@router.post("/retrain", response_model=RetrainResponse, status_code=202)
def retrain(
    background: BackgroundTasks,
    estimator: str = DEFAULT_RECOMMENDED_ESTIMATOR,
    feature_set: str = DEFAULT_RECOMMENDED_FEATURE_SET,
) -> RetrainResponse:
    if estimator not in ESTIMATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown estimator '{estimator}'. Choose: {list(ESTIMATORS)}",
        )
    if feature_set not in {"baseline", "feature_v2"}:
        raise HTTPException(
            status_code=400,
            detail="Unknown feature_set. Choose: ['baseline', 'feature_v2']",
        )
    background.add_task(_retrain_job, estimator, feature_set)
    return RetrainResponse(
        status="scheduled",
        message=(
            f"Retrain ({estimator}/{feature_set}) started in background. "
            "Check API logs for completion."
        ),
    )
