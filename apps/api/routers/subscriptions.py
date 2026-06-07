"""GET /subscriptions — recurring debits with stable amount + cadence."""
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.feedback import (
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SUBSCRIPTION_HIDDEN,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.ml.subscriptions import detect_subscriptions
from finance.transactions.normalization import normalize_merchant

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionRow(BaseModel):
    merchant: str
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


def _hidden_subscription_merchants(session: Session) -> set[str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key).where(
            MlFeedbackEvent.event_type == EVENT_SUBSCRIPTION_HIDDEN,
            MlFeedbackEvent.entity_type == "subscription_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        )
    ).scalars()
    return {str(row) for row in rows if row}


@router.get("", response_model=list[SubscriptionRow])
def list_subscriptions(
    session: Session = Depends(get_session),
    min_occurrences: int = Query(default=2, ge=2, le=12),
    amount_tol: float = Query(default=0.10, ge=0.0, le=0.5),
    day_tol: int = Query(default=5, ge=1, le=15),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[SubscriptionRow]:
    rows = session.execute(select(Transaction)).scalars().all()
    if not rows:
        return []
    df = pd.DataFrame(
        [
            {
                "booking_date": r.booking_date,
                "amount": float(r.amount),
                "direction": r.direction,
                "merchant": r.merchant or "",
                "category": r.category,
                "is_transfer": r.is_transfer,
            }
            for r in rows
        ]
    )
    subs = detect_subscriptions(
        df,
        min_occurrences=min_occurrences,
        amount_tol=amount_tol,
        day_tol=day_tol,
    )
    hidden = _hidden_subscription_merchants(session)
    return [
        SubscriptionRow(
            merchant=s.merchant,
            cadence=s.cadence,
            median_amount=s.median_amount,
            occurrences=s.occurrences,
            last_seen=s.last_seen.date()
            if hasattr(s.last_seen, "date") else s.last_seen,
            estimated_monthly_cost=s.estimated_monthly_cost,
            confidence=s.confidence,
        )
        for s in subs
        if s.confidence >= min_confidence
        and normalize_merchant(s.merchant) not in hidden
    ]


@router.post("/feedback", response_model=FeedbackResponse)
def record_subscription_feedback(
    req: SubscriptionFeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    event_type = (
        EVENT_SUBSCRIPTION_CONFIRMED
        if req.action == "confirm"
        else EVENT_SUBSCRIPTION_HIDDEN
    )
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=event_type,
            entity_type="subscription_merchant",
            entity_key=normalize_merchant(req.merchant),
            source="subscription_detector",
        ),
    )
    session.commit()
    session.refresh(event)
    return FeedbackResponse(id=event.id)
