"""GET /anomalies — flagged transactions with severity score."""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.errors import not_found
from finance.db import get_session
from finance.ml.anomaly.service import (
    AnomalyDirection,
    AnomalyMode,
    AnomalyReviewRow,
    list_anomaly_rows,
)
from finance.ml.anomaly.service import (
    record_anomaly_feedback as record_anomaly_feedback_event,
)

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyRow(BaseModel):
    id: int
    booking_date: date
    amount: Decimal
    direction: str
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    title: str
    category: str | None
    severity: float
    priority_score: float
    anomaly_type: str
    reasons: list[str]
    reason_codes: list[str]
    merchant_occurrences: int
    merchant_median_amount: float
    is_recurring_merchant: bool
    feedback_status: Literal["relevant", "not_relevant", "ignore_merchant"] | None = None


class AnomalyFeedbackRequest(BaseModel):
    action: Literal["relevant", "not_relevant", "ignore_merchant"]


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    id: int | None = None


def _to_response(row: AnomalyReviewRow) -> AnomalyRow:
    return AnomalyRow(
        id=row.id,
        booking_date=row.booking_date,
        amount=row.amount,
        direction=row.direction,
        merchant=row.merchant,
        merchant_display=row.merchant_display,
        merchant_canonical_key=row.merchant_canonical_key,
        title=row.title,
        category=row.category,
        severity=row.severity,
        priority_score=row.priority_score,
        anomaly_type=row.anomaly_type,
        reasons=row.reasons,
        reason_codes=row.reason_codes,
        merchant_occurrences=row.merchant_occurrences,
        merchant_median_amount=row.merchant_median_amount,
        is_recurring_merchant=row.is_recurring_merchant,
        feedback_status=row.feedback_status,
    )


@router.get("", response_model=list[AnomalyRow])
def list_anomalies(
    session: Session = Depends(get_session),
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = Query(default=0.05, ge=0.005, le=0.3),
    direction: AnomalyDirection | None = Query(
        default="debit",
        pattern="^(debit|credit|both)$",
    ),
    limit: int = Query(default=50, le=500),
    mode: AnomalyMode = Query(default="review"),
    include_model_only: bool = Query(default=False),
) -> list[AnomalyRow]:
    return [
        _to_response(row)
        for row in list_anomaly_rows(
            session,
            date_from=date_from,
            date_to=date_to,
            contamination=contamination,
            direction=direction,
            limit=limit,
            mode=mode,
            include_model_only=include_model_only,
        )
    ]


@router.post("/{transaction_id}/feedback", response_model=FeedbackResponse)
def record_anomaly_feedback(
    transaction_id: int,
    req: AnomalyFeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    event = record_anomaly_feedback_event(
        session,
        transaction_id=transaction_id,
        action=req.action,
    )
    if event is None:
        raise not_found("Transaction not found")
    return FeedbackResponse(id=event.id)
