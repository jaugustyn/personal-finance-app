"""POST /ml/classify  — classify a single transaction-like payload.
POST /ml/reclassify — bulk-predict for rows without a ground-truth category.
POST /ml/retrain    — refit the classifier on current DB labels (background).
"""
import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import joblib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.db import SessionLocal, get_session
from finance.ml.classification.artifacts import build_model_artifact
from finance.ml.classification.policy import (
    ClassificationPolicy,
    policy_from_report,
)
from finance.ml.classification.predict import (
    ClassifierNotAvailable,
    get_classifier,
    predict_transaction,
    reclassify_unlabelled,
)
from finance.ml.classification.status import (
    CONFIDENCE_RECOMMENDATION_THRESHOLD,
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
from finance.ml.classification.train import (
    ESTIMATORS,
    build_evidence_report,
    fit_final,
    load_training_set,
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


class ClassifyRequest(BaseModel):
    merchant: str = ""
    title: str = ""
    amount: Decimal
    booking_date: date
    source: str = "unknown"
    transaction_type: str = "purchase"
    direction: Literal["debit", "credit"] | None = None
    is_transfer: bool = False
    use_llm_fallback: bool = False
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)


class ClassificationDecisionResponse(BaseModel):
    action: str
    reason_code: str
    threshold_used: float
    review_floor: float
    category: str | None = None
    confidence: float | None = None
    category_candidate: bool


class ClassifyResponse(BaseModel):
    category: str
    confidence: float | None = None
    source: str = "model"
    model_category: str | None = None
    threshold: float = 0.55
    threshold_used: float = 0.55
    fallback_used: bool = False
    top_predictions: list[dict[str, Any]] = Field(default_factory=list)
    recommended_action: str = "review"
    classification_decision: ClassificationDecisionResponse


class ReclassifyResponse(BaseModel):
    updated: int


class RetrainResponse(BaseModel):
    status: str
    message: str


class MlFeedbackRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=48)
    transaction_id: int | None = None
    entity_type: str | None = Field(default=None, max_length=48)
    entity_key: str | None = Field(default=None, max_length=255)
    predicted_category: str | None = None
    final_category: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = None
    model_artifact: str | None = None


class MlFeedbackResponse(BaseModel):
    id: int | None = None
    status: str = "recorded"


class MlMetricSummary(BaseModel):
    model: str | None = None
    macro_f1: float | None = None
    weighted_f1: float | None = None
    coverage_at_055: float | None = None
    accuracy_at_055: float | None = None


class MlModelComparison(BaseModel):
    estimator: str
    feature_set: str
    rank: int | None = None
    macro_f1: float | None = None
    weighted_f1: float | None = None
    coverage_at_055: float | None = None
    accuracy_at_055: float | None = None
    time_holdout_macro_f1: float | None = None
    merchant_group_macro_f1: float | None = None
    stability_score: float | None = None
    confidence_note: str | None = None
    skipped: bool = False
    error: str | None = None
    is_recommended: bool = False
    is_current: bool = False


class MlModelRecommendation(BaseModel):
    estimator: str
    feature_set: str
    reason_code: str
    action_codes: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    macro_f1: float | None = None
    weighted_f1: float | None = None
    coverage_at_055: float | None = None
    accuracy_at_055: float | None = None
    confidence_threshold: float = CONFIDENCE_RECOMMENDATION_THRESHOLD
    based_on_report: bool = False
    feature_decision_reason: str | None = None


class MlModelStatus(BaseModel):
    exists: bool
    path: str
    updated_at: str | None = None
    estimator: str | None = None
    feature_set: str | None = None
    classes: list[str] = Field(default_factory=list)
    known_categories: list[str] = Field(default_factory=list)
    missing_categories: list[str] = Field(default_factory=list)
    extra_classes: list[str] = Field(default_factory=list)
    n_total_labelled: int | None = None
    n_classes: int | None = None
    report_path: str | None = None
    report_updated_at: str | None = None
    best_model: MlMetricSummary | None = None
    load_error: str | None = None
    artifact_metadata: dict[str, Any] = Field(default_factory=dict)
    compatibility_warnings: list[str] = Field(default_factory=list)
    retrain_signal: dict[str, Any] | None = None


class MlReadinessResponse(BaseModel):
    level: str
    total_labelled: int
    minimum_total: int
    recommended_total: int
    ideal_total: int
    minimum_per_category: int
    recommended_per_category: int
    strong_per_category: int
    category_counts: dict[str, int]
    below_minimum_per_category: list[str]
    below_recommended_per_category: list[str]
    date_span_months: int | None = None
    recommended_history_months: str
    training_labels_source: str
    category_predicted_is_ground_truth: bool
    next_review_priority: list[str]


class MlLatestReportResponse(BaseModel):
    path: str | None = None
    updated_at: str | None = None
    report: dict[str, Any] | None = None


class MlComparisonResponse(BaseModel):
    models: list[MlModelComparison] = Field(default_factory=list)
    recommendation: MlModelRecommendation


class MlDashboardResponse(BaseModel):
    status: MlModelStatus
    readiness: MlReadinessResponse
    latest_report: MlLatestReportResponse
    model_comparison: list[MlModelComparison] = Field(default_factory=list)
    recommendation: MlModelRecommendation
    validation_slices: dict[str, Any] = Field(default_factory=dict)
    confidence_policy: dict[str, Any] = Field(default_factory=dict)
    feedback_quality: dict[str, Any] = Field(default_factory=dict)
    feedback_report: dict[str, Any] = Field(default_factory=dict)
    retrain_signal: dict[str, Any] = Field(default_factory=dict)
    confusion_hotspots: list[dict[str, Any]] = Field(default_factory=list)


class ReviewQueueItemResponse(BaseModel):
    transaction_id: int
    booking_date: date
    merchant: str
    title: str
    amount: Decimal
    currency: str
    direction: str
    predicted_category: str | None = None
    confidence: float | None = None
    decision_action: str
    decision_reason: str
    priority_score: float
    priority_components: dict[str, float]
    reason_codes: list[str]


class FeedbackReportResponse(BaseModel):
    quality: dict[str, Any]
    feedback_events_since_model: int
    feedback_events_used_in_training: int | None = None
    feedback_events_not_yet_in_model: int | None = None
    feedback_coverage: float | None = None
    coverage_basis: str
    labels_used_in_current_model: int | None = None
    current_label_count: int | None = None
    new_labels_since_training: int | None = None
    new_labels_since_training_ratio: float | None = None
    top_corrected_merchants: list[dict[str, Any]] = Field(default_factory=list)
    category_corrections: list[dict[str, Any]] = Field(default_factory=list)
    rejection_by_category: list[dict[str, Any]] = Field(default_factory=list)


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
            transaction_type=req.transaction_type,
            direction=req.direction,
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
    """Background job: load labelled rows, evaluate, refit, persist, reset cache."""
    try:
        with SessionLocal() as session:
            df = load_training_set(session)
        labelled = int(df["category"].notna().sum()) if not df.empty else 0
        logger.info("Retrain: %d labelled rows", labelled)
        if labelled < 8:
            logger.warning("Retrain aborted: too few labelled rows (%d).", labelled)
            return
        report = build_evidence_report(df)
        logger.info("Retrain CV report: %s", report.get("models", {}))
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / (
            f"classification_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        pipe = fit_final(df, estimator, feature_set=feature_set)
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            build_model_artifact(
                estimator=estimator,
                feature_set=feature_set,
                pipeline=pipe,
                report=report,
            ),
            MODEL_PATH,
        )
        get_classifier.cache_clear()  # type: ignore[attr-defined]
        logger.info(
            "Retrain: model saved to %s; report saved to %s",
            MODEL_PATH,
            report_path,
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
