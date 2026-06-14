"""Shared subscription review service used by API and LLM tools."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.feedback import (
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SUBSCRIPTION_HIDDEN,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.ml.subscriptions.detector import detect_subscriptions
from finance.transactions.normalization import normalize_merchant

SubscriptionFeedbackAction = Literal["confirm", "hide"]


@dataclass(frozen=True)
class SubscriptionReviewRow:
    merchant: str
    cadence: str
    median_amount: float
    occurrences: int
    last_seen: date
    estimated_monthly_cost: float
    confidence: float


def hidden_subscription_merchants(session: Session) -> set[str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key).where(
            MlFeedbackEvent.event_type == EVENT_SUBSCRIPTION_HIDDEN,
            MlFeedbackEvent.entity_type == "subscription_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        )
    ).scalars()
    return {str(row) for row in rows if row}


def _transaction_frame(session: Session) -> pd.DataFrame:
    rows = session.execute(select(Transaction)).scalars().all()
    return pd.DataFrame(
        [
            {
                "booking_date": row.booking_date,
                "amount": float(row.amount),
                "direction": row.direction,
                "merchant": row.merchant or "",
                "category": row.category,
                "is_transfer": row.is_transfer,
            }
            for row in rows
        ]
    )


def _to_row(sub) -> SubscriptionReviewRow:
    last_seen = sub.last_seen.date() if hasattr(sub.last_seen, "date") else sub.last_seen
    return SubscriptionReviewRow(
        merchant=sub.merchant,
        cadence=sub.cadence,
        median_amount=float(sub.median_amount),
        occurrences=int(sub.occurrences),
        last_seen=last_seen,
        estimated_monthly_cost=float(sub.estimated_monthly_cost),
        confidence=float(sub.confidence),
    )


def list_subscription_rows(
    session: Session,
    *,
    min_occurrences: int = 2,
    amount_tol: float = 0.10,
    day_tol: int = 5,
    min_confidence: float = 0.0,
    include_hidden: bool = False,
) -> list[SubscriptionReviewRow]:
    df = _transaction_frame(session)
    if df.empty:
        return []
    subs = detect_subscriptions(
        df,
        min_occurrences=min_occurrences,
        amount_tol=amount_tol,
        day_tol=day_tol,
    )
    hidden = set() if include_hidden else hidden_subscription_merchants(session)
    return [
        _to_row(sub)
        for sub in subs
        if sub.confidence >= min_confidence
        and normalize_merchant(sub.merchant) not in hidden
    ]


def record_subscription_feedback(
    session: Session,
    *,
    merchant: str,
    action: SubscriptionFeedbackAction,
) -> MlFeedbackEvent:
    event_type = (
        EVENT_SUBSCRIPTION_CONFIRMED if action == "confirm" else EVENT_SUBSCRIPTION_HIDDEN
    )
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=event_type,
            entity_type="subscription_merchant",
            entity_key=normalize_merchant(merchant),
            source="subscription_detector",
        ),
    )
    session.commit()
    session.refresh(event)
    return event
