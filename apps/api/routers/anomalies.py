"""Anomaly review queue and assessment history."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.errors import not_found
from finance.db import get_session
from finance.ml.anomaly.service import (
    AnomalyDirection,
    AnomalyReviewRow,
    AnomalyReviewState,
    get_anomaly_review_result,
)
from finance.ml.anomaly.service import (
    record_anomaly_feedback as record_anomaly_feedback_event,
)

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyRow(BaseModel):
    id: int
    booking_date: date
    amount: Decimal
    base_currency: str
    direction: str
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    title: str
    category: str | None
    severity: float | None
    priority_score: float | None
    anomaly_type: str | None
    reasons: list[str]
    reason_codes: list[str]
    merchant_occurrences: int
    merchant_median_amount: float
    is_recurring_merchant: bool
    review_status: Literal["relevant", "not_relevant"] | None = None
    reviewed_at: datetime | None = None
    currently_detected: bool


class AnomalyListResponse(BaseModel):
    items: list[AnomalyRow]
    total: int
    pending_total: int
    reviewed_total: int


class AnomalyFeedbackRequest(BaseModel):
    action: Literal["relevant", "not_relevant", "restore"]


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    id: int | None = None


def _to_response(row: AnomalyReviewRow) -> AnomalyRow:
    return AnomalyRow(
        id=row.id,
        booking_date=row.booking_date,
        amount=row.amount,
        base_currency=row.base_currency,
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
        review_status=row.review_status,
        reviewed_at=row.reviewed_at,
        currently_detected=row.currently_detected,
    )


@router.get("", response_model=AnomalyListResponse)
def list_anomalies(
    session: Session = Depends(get_session),
    review_state: AnomalyReviewState = Query(default="pending"),
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = Query(default=0.05, ge=0.005, le=0.3),
    direction: AnomalyDirection | None = Query(
        default="debit",
        pattern="^(debit|credit|both)$",
    ),
    limit: int | None = Query(default=None, le=500),
) -> AnomalyListResponse:
    result = get_anomaly_review_result(
        session,
        review_state=review_state,
        date_from=date_from,
        date_to=date_to,
        contamination=contamination,
        direction=direction,
        limit=limit,
    )
    return AnomalyListResponse(
        items=[_to_response(row) for row in result.items],
        total=result.total,
        pending_total=result.pending_total,
        reviewed_total=result.reviewed_total,
    )


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
