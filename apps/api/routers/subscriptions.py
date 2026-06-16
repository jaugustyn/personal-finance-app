"""GET /subscriptions — recurring debits with stable amount + cadence."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.ml.subscriptions.service import (
    SubscriptionReviewRow,
    list_subscription_rows,
    record_subscription_feedback as record_subscription_feedback_event,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionRow(BaseModel):
    merchant: str
    merchant_key: str
    cadence: str
    median_amount: float
    occurrences: int
    last_seen: date
    estimated_monthly_cost: float
    confidence: float


class SubscriptionFeedbackRequest(BaseModel):
    merchant: str
    action: Literal["confirm", "hide"]


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    id: int | None = None


def _to_response(row: SubscriptionReviewRow) -> SubscriptionRow:
    return SubscriptionRow(
        merchant=row.merchant,
        merchant_key=row.merchant_key,
        cadence=row.cadence,
        median_amount=row.median_amount,
        occurrences=row.occurrences,
        last_seen=row.last_seen,
        estimated_monthly_cost=row.estimated_monthly_cost,
        confidence=row.confidence,
    )


@router.get("", response_model=list[SubscriptionRow])
def list_subscriptions(
    session: Session = Depends(get_session),
    min_occurrences: int = Query(default=2, ge=2, le=12),
    amount_tol: float = Query(default=0.10, ge=0.0, le=0.5),
    day_tol: int = Query(default=5, ge=1, le=15),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[SubscriptionRow]:
    return [
        _to_response(row)
        for row in list_subscription_rows(
            session,
            min_occurrences=min_occurrences,
            amount_tol=amount_tol,
            day_tol=day_tol,
            min_confidence=min_confidence,
        )
    ]


@router.post("/feedback", response_model=FeedbackResponse)
def record_subscription_feedback(
    req: SubscriptionFeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    event = record_subscription_feedback_event(
        session,
        merchant=req.merchant,
        action=req.action,
    )
    return FeedbackResponse(id=event.id)
