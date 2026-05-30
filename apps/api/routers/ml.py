"""POST /ml/classify  — classify a single transaction-like payload.
POST /ml/reclassify — bulk-predict for rows without a ground-truth category.
POST /ml/retrain    — refit the classifier on current DB labels (background).
"""
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import joblib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.db import SessionLocal, get_session
from finance.ml.classification.predict import (
    ClassifierNotAvailable,
    get_classifier,
    predict_transaction,
    reclassify_unlabelled,
)
from finance.ml.classification.train import (
    ESTIMATORS,
    evaluate,
    fit_final,
    load_training_set,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])

MODEL_PATH = Path("data/models/classifier_latest.joblib")


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
    fallback_used: bool = False


class ReclassifyResponse(BaseModel):
    updated: int


class RetrainResponse(BaseModel):
    status: str
    message: str


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
        fallback_used=result.fallback_used,
    )


@router.post("/reclassify", response_model=ReclassifyResponse)
def reclassify(session: Session = Depends(get_session)) -> ReclassifyResponse:
    try:
        n = reclassify_unlabelled(session)
    except ClassifierNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReclassifyResponse(updated=n)


def _retrain_job(estimator: str, feature_set: str = "baseline") -> None:
    """Background job: load labelled rows, evaluate, refit, persist, reset cache."""
    try:
        with SessionLocal() as session:
            df = load_training_set(session)
        labelled = int(df["category"].notna().sum()) if not df.empty else 0
        logger.info("Retrain: %d labelled rows", labelled)
        if labelled < 8:
            logger.warning("Retrain aborted: too few labelled rows (%d).", labelled)
            return
        report = evaluate(df)
        logger.info("Retrain CV report: %s", report.get("models", {}))
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
        logger.info("Retrain: model saved to %s", MODEL_PATH)
    except Exception:
        logger.exception("Retrain job failed")


@router.post("/retrain", response_model=RetrainResponse, status_code=202)
def retrain(
    background: BackgroundTasks,
    estimator: str = "linear_svc",
    feature_set: str = "baseline",
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
