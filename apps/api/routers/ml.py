"""POST /ml/classify  — classify a single transaction-like payload.
POST /ml/reclassify — bulk-predict for rows without a ground-truth category.
POST /ml/retrain    — refit the classifier on current DB labels (background).
"""
import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import joblib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.db import SessionLocal, get_session
from finance.domain.enums import Category
from finance.ml.feedback import (
    FeedbackEventInput,
    confusion_hotspots,
    feedback_quality,
    record_feedback_event,
)
from finance.ml.classification.predict import (
    ClassifierNotAvailable,
    get_classifier,
    predict_transaction,
    reclassify_unlabelled,
)
from finance.ml.classification.train import (
    ESTIMATORS,
    build_label_readiness,
    build_evidence_report,
    fit_final,
    load_training_set,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])

MODEL_PATH = Path("data/models/classifier_latest.joblib")
REPORTS_DIR = Path("data/reports")
CONFIDENCE_RECOMMENDATION_THRESHOLD = 0.55
DEFAULT_RECOMMENDED_ESTIMATOR = "linear_svc_calibrated"
DEFAULT_RECOMMENDED_FEATURE_SET = "feature_v2"
CALIBRATED_ESTIMATORS = {"linear_svc_calibrated", "logreg"}


class ClassifyRequest(BaseModel):
    merchant: str = ""
    title: str = ""
    amount: Decimal
    booking_date: date
    source: str = "unknown"
    transaction_type: str = "purchase"
    use_llm_fallback: bool = False
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)


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
    confusion_hotspots: list[dict[str, Any]] = Field(default_factory=list)


def _iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _latest_report_path() -> Path | None:
    reports = sorted(REPORTS_DIR.glob("classification_*.json"))
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)


def _load_latest_report() -> MlLatestReportResponse:
    path = _latest_report_path()
    if path is None:
        return MlLatestReportResponse()
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report = {"error": str(exc)}
    return MlLatestReportResponse(
        path=str(path),
        updated_at=_iso_mtime(path),
        report=report,
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence_point(
    model_report: dict[str, Any],
    threshold: float = CONFIDENCE_RECOMMENDATION_THRESHOLD,
) -> tuple[float | None, float | None]:
    for point in model_report.get("confidence_curve") or []:
        if abs(float(point.get("threshold", -1.0)) - threshold) < 1e-9:
            return (
                _as_float(point.get("coverage")),
                _as_float(point.get("accuracy_on_covered")),
            )
    return None, None


def _iter_model_reports(
    report: dict[str, Any] | None,
) -> list[tuple[str, str, dict[str, Any]]]:
    if not report:
        return []
    out: list[tuple[str, str, dict[str, Any]]] = []
    feature_variants = report.get("feature_variants")
    if isinstance(feature_variants, dict):
        for feature_set, feature_report in feature_variants.items():
            if not isinstance(feature_report, dict):
                continue
            models = feature_report.get("models") or {}
            if not isinstance(models, dict):
                continue
            for estimator, model_report in models.items():
                if isinstance(model_report, dict):
                    out.append((str(feature_set), str(estimator), model_report))
    if out:
        return out

    models = report.get("models") or {}
    if isinstance(models, dict):
        for estimator, model_report in models.items():
            if isinstance(model_report, dict):
                out.append(("baseline", str(estimator), model_report))
    return out


def _recommended_feature_set(
    report: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not report:
        return None, None
    decision = report.get("feature_decision")
    if not isinstance(decision, dict):
        return None, None
    feature_set = decision.get("recommended_feature_set")
    raw_reason = decision.get("reason")
    reason = raw_reason if isinstance(raw_reason, str) else None
    if feature_set not in {"baseline", "feature_v2"}:
        return None, reason
    return str(feature_set), reason


def _slice_macro_f1(
    report: dict[str, Any] | None,
    slice_name: str,
    estimator: str,
) -> float | None:
    if not report:
        return None
    validation = report.get("validation_slices")
    if not isinstance(validation, dict):
        return None
    slice_report = validation.get(slice_name)
    if not isinstance(slice_report, dict) or slice_report.get("skipped"):
        return None
    models = slice_report.get("models")
    if not isinstance(models, dict):
        return None
    model = models.get(estimator)
    if not isinstance(model, dict) or model.get("skipped"):
        return None
    return _as_float(model.get("macro_f1"))


def _stability_score(
    report: dict[str, Any] | None,
    estimator: str,
) -> tuple[float | None, float | None, float | None]:
    time_macro = _slice_macro_f1(report, "time_holdout", estimator)
    group_macro = _slice_macro_f1(report, "merchant_group_holdout", estimator)
    values = [value for value in (time_macro, group_macro) if value is not None]
    score = sum(values) / len(values) if values else None
    return time_macro, group_macro, score


def _model_comparison(
    report: dict[str, Any] | None,
    status: MlModelStatus | None = None,
) -> list[MlModelComparison]:
    current_estimator = status.estimator if status else None
    current_feature_set = (status.feature_set or "baseline") if status else None
    rows: list[MlModelComparison] = []
    for feature_set, estimator, model_report in _iter_model_reports(report):
        coverage, accuracy = _confidence_point(model_report)
        time_macro, group_macro, stability = _stability_score(report, estimator)
        rows.append(
            MlModelComparison(
                estimator=estimator,
                feature_set=feature_set,
                macro_f1=_as_float(model_report.get("macro_f1")),
                weighted_f1=_as_float(model_report.get("weighted_f1")),
                coverage_at_055=coverage,
                accuracy_at_055=accuracy,
                time_holdout_macro_f1=time_macro,
                merchant_group_macro_f1=group_macro,
                stability_score=stability,
                confidence_note=model_report.get("confidence_note"),
                skipped=bool(model_report.get("skipped")),
                error=model_report.get("error"),
                is_current=(
                    estimator == current_estimator and feature_set == current_feature_set
                ),
            )
        )

    rows.sort(
        key=lambda row: (
            row.skipped,
            -(row.stability_score or 0.0),
            -(row.macro_f1 or 0.0),
            -(row.weighted_f1 or 0.0),
            row.feature_set,
            row.estimator,
        )
    )
    for idx, row in enumerate(rows, start=1):
        row.rank = idx
    return rows


def _recommend_model(
    report: dict[str, Any] | None,
    comparison: list[MlModelComparison],
    status: MlModelStatus,
    readiness: MlReadinessResponse,
) -> MlModelRecommendation:
    actionable = [
        row
        for row in comparison
        if not row.skipped and not row.estimator.startswith("dummy")
    ]
    target_feature_set, feature_reason = _recommended_feature_set(report)

    if not actionable:
        recommendation = MlModelRecommendation(
            estimator=DEFAULT_RECOMMENDED_ESTIMATOR,
            feature_set=target_feature_set or DEFAULT_RECOMMENDED_FEATURE_SET,
            reason_code="no_report",
            action_codes=["train_recommended"],
            warning_codes=["no_report"],
            based_on_report=False,
            feature_decision_reason=feature_reason,
        )
    else:
        if target_feature_set:
            pool = [row for row in actionable if row.feature_set == target_feature_set]
        else:
            pool = []
        if not pool:
            pool = actionable

        best = max(
            pool,
            key=lambda row: (
                row.stability_score if row.stability_score is not None else -1.0,
                row.macro_f1 or 0.0,
            ),
        )
        best_macro = best.macro_f1 or 0.0
        calibrated_pool = [
            row
            for row in pool
            if row.estimator in CALIBRATED_ESTIMATORS
            and (row.macro_f1 or 0.0) >= best_macro - 0.02
        ]
        if calibrated_pool:
            selected = max(
                calibrated_pool,
                key=lambda row: (
                    row.stability_score if row.stability_score is not None else -1.0,
                    row.macro_f1 or 0.0,
                ),
            )
            reason_code = (
                "best_calibrated_macro_f1"
                if selected.estimator == best.estimator
                else "prefer_calibrated_close"
            )
        else:
            selected = best
            reason_code = "best_macro_f1"

        recommendation = MlModelRecommendation(
            estimator=selected.estimator,
            feature_set=selected.feature_set,
            reason_code=reason_code,
            macro_f1=selected.macro_f1,
            weighted_f1=selected.weighted_f1,
            coverage_at_055=selected.coverage_at_055,
            accuracy_at_055=selected.accuracy_at_055,
            based_on_report=True,
            feature_decision_reason=feature_reason,
        )

    for row in comparison:
        row.is_recommended = (
            row.estimator == recommendation.estimator
            and row.feature_set == recommendation.feature_set
        )

    if not status.exists or status.load_error:
        recommendation.action_codes.append("train_recommended")
    elif (
        status.estimator != recommendation.estimator
        or (status.feature_set or "baseline") != recommendation.feature_set
    ):
        recommendation.action_codes.append("train_recommended")
    else:
        recommendation.action_codes.append("current_matches_recommended")

    recommendation.action_codes.append("reclassify_after_training")

    if readiness.below_recommended_per_category:
        recommendation.action_codes.append("balance_categories")
    if status.missing_categories:
        recommendation.warning_codes.append("missing_categories")
    if readiness.level in {"insufficient", "minimum"}:
        recommendation.warning_codes.append("limited_labels")
    if not report:
        recommendation.warning_codes.append("no_report")

    recommendation.action_codes = list(dict.fromkeys(recommendation.action_codes))
    recommendation.warning_codes = list(dict.fromkeys(recommendation.warning_codes))
    return recommendation


def _best_metric_summary(report: dict[str, Any] | None) -> MlMetricSummary | None:
    if not report:
        return None
    models = report.get("models") or {}
    candidates = {
        name: info
        for name, info in models.items()
        if not name.startswith("dummy") and not info.get("skipped")
    }
    if not candidates:
        return None
    best_name = max(
        candidates,
        key=lambda name: float(candidates[name].get("macro_f1") or 0.0),
    )
    best = candidates[best_name]
    coverage, accuracy = _confidence_point(best)
    return MlMetricSummary(
        model=best_name,
        macro_f1=best.get("macro_f1"),
        weighted_f1=best.get("weighted_f1"),
        coverage_at_055=coverage,
        accuracy_at_055=accuracy,
    )


def _extract_model_classes(pipe: Any, report: dict[str, Any] | None) -> list[str]:
    named_steps = getattr(pipe, "named_steps", {}) if pipe is not None else {}
    clf = named_steps.get("clf") if isinstance(named_steps, dict) else None
    raw_classes = getattr(clf, "classes_", None)
    classes = list(raw_classes) if raw_classes is not None else []
    if not classes and report:
        classes = list(report.get("labels") or [])
    return sorted(str(item) for item in classes)


def _model_status_from_disk() -> MlModelStatus:
    known_categories = sorted(category.value for category in Category)
    status = MlModelStatus(
        exists=MODEL_PATH.exists(),
        path=str(MODEL_PATH),
        updated_at=_iso_mtime(MODEL_PATH),
        known_categories=known_categories,
    )
    latest_report = _load_latest_report()
    latest_report_data = (
        latest_report.report if isinstance(latest_report.report, dict) else None
    )

    if not MODEL_PATH.exists():
        status.report_path = latest_report.path
        status.report_updated_at = latest_report.updated_at
        status.best_model = _best_metric_summary(latest_report_data)
        status.missing_categories = known_categories
        return status

    try:
        artifact = joblib.load(MODEL_PATH)
        report = artifact.get("report") if isinstance(artifact, dict) else None
        report = report if isinstance(report, dict) else latest_report_data
        pipe = artifact.get("pipeline") if isinstance(artifact, dict) else artifact
        status.estimator = artifact.get("estimator") if isinstance(artifact, dict) else None
        status.feature_set = artifact.get("feature_set") if isinstance(artifact, dict) else None
        status.classes = _extract_model_classes(pipe, report)
        status.n_total_labelled = report.get("n_total_labelled") if report else None
        status.n_classes = report.get("n_classes") if report else None
        status.best_model = _best_metric_summary(report)
    except Exception as exc:  # noqa: BLE001
        status.load_error = str(exc)
        if latest_report_data:
            status.classes = sorted(str(item) for item in latest_report_data.get("labels") or [])
            status.n_total_labelled = latest_report_data.get("n_total_labelled")
            status.n_classes = latest_report_data.get("n_classes")
        status.best_model = _best_metric_summary(latest_report_data)

    observed = set(status.classes)
    known = set(known_categories)
    status.missing_categories = sorted(known - observed)
    status.extra_classes = sorted(observed - known)
    status.report_path = latest_report.path
    status.report_updated_at = latest_report.updated_at
    return status


def _readiness(session: Session) -> MlReadinessResponse:
    df = load_training_set(session)
    data = build_label_readiness(df)
    return MlReadinessResponse(**data)


@router.get("/status", response_model=MlModelStatus)
def model_status() -> MlModelStatus:
    return _model_status_from_disk()


@router.get("/readiness", response_model=MlReadinessResponse)
def readiness(session: Session = Depends(get_session)) -> MlReadinessResponse:
    return _readiness(session)


@router.get("/report/latest", response_model=MlLatestReportResponse)
def latest_report() -> MlLatestReportResponse:
    return _load_latest_report()


@router.get("/comparison", response_model=MlComparisonResponse)
def model_comparison(
    session: Session = Depends(get_session),
) -> MlComparisonResponse:
    status = _model_status_from_disk()
    readiness = _readiness(session)
    latest = _load_latest_report()
    report = latest.report if isinstance(latest.report, dict) else None
    comparison = _model_comparison(report, status)
    return MlComparisonResponse(
        models=comparison,
        recommendation=_recommend_model(report, comparison, status, readiness),
    )


@router.get("/dashboard", response_model=MlDashboardResponse)
def dashboard(session: Session = Depends(get_session)) -> MlDashboardResponse:
    status = _model_status_from_disk()
    readiness = _readiness(session)
    latest = _load_latest_report()
    report = latest.report if isinstance(latest.report, dict) else None
    comparison = _model_comparison(report, status)
    return MlDashboardResponse(
        status=status,
        readiness=readiness,
        latest_report=latest,
        model_comparison=comparison,
        recommendation=_recommend_model(report, comparison, status, readiness),
        validation_slices=report.get("validation_slices", {}) if report else {},
        confidence_policy=report.get("confidence_policy", {}) if report else {},
        feedback_quality=feedback_quality(session),
        confusion_hotspots=confusion_hotspots(session),
    )


@router.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
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
    try:
        n = reclassify_unlabelled(session)
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
            {
                "estimator": estimator,
                "feature_set": feature_set,
                "pipeline": pipe,
                "report": report,
            },
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
