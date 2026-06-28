"""GET /subscriptions — recurring debits with stable amount + cadence."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.ml.subscriptions.service import (
    SubscriptionOverview,
    SubscriptionReviewRow,
    list_subscription_rows,
    record_subscription_feedback as record_subscription_feedback_event,
    subscription_overview,
    upsert_subscription_preference,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionRow(BaseModel):
    merchant: str
    merchant_key: str
    display_name: str
    currency: str
    base_currency: str
    cadence: str
    median_amount: float
    occurrences: int
    last_seen: date
    next_expected_date: date | None
    estimated_monthly_cost_original: float
    estimated_monthly_cost: float
    confidence: float
    status: str
    source: str
    previous_amount: float | None
    current_amount: float | None
    price_change_pct: float | None
    price_change_annual_impact: float | None
    evidence: dict[str, object]
    is_confirmed: bool
    is_ignored: bool


class SubscriptionFeedbackRequest(BaseModel):
    merchant: str
    action: Literal["confirm", "hide"]


class SubscriptionPreferenceRequest(BaseModel):
    subscription_key: str
    action: Literal["confirm", "ignore", "not_subscription", "update"] = "update"
    display_name: str | None = None
    cadence_override: (
        Literal["weekly", "biweekly", "monthly", "yearly", "unknown"] | None
    ) = None


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    id: int | None = None


class PreferenceResponse(BaseModel):
    status: str = "saved"
    id: int


class UpcomingPaymentRow(BaseModel):
    subscription_key: str
    display_name: str
    due_date: date
    amount: float
    currency: str
    amount_base: float
    base_currency: str
    status: str


class SubscriptionOverviewResponse(BaseModel):
    monthly_total: float
    yearly_total: float
    next_30_days_count: int
    next_30_days_total: float
    base_currency: str
    upcoming: list[UpcomingPaymentRow]


def _to_response(row: SubscriptionReviewRow) -> SubscriptionRow:
    return SubscriptionRow(
        merchant=row.merchant,
        merchant_key=row.merchant_key,
        display_name=row.display_name,
        currency=row.currency,
        base_currency=row.base_currency,
        cadence=row.cadence,
        median_amount=row.median_amount,
        occurrences=row.occurrences,
        last_seen=row.last_seen,
        next_expected_date=row.next_expected_date,
        estimated_monthly_cost_original=row.estimated_monthly_cost_original,
        estimated_monthly_cost=row.estimated_monthly_cost,
        confidence=row.confidence,
        status=row.status,
        source=row.source,
        previous_amount=row.previous_amount,
        current_amount=row.current_amount,
        price_change_pct=row.price_change_pct,
        price_change_annual_impact=row.price_change_annual_impact,
        evidence=row.evidence,
        is_confirmed=row.is_confirmed,
        is_ignored=row.is_ignored,
    )


def _overview_response(overview: SubscriptionOverview) -> SubscriptionOverviewResponse:
    return SubscriptionOverviewResponse(
        monthly_total=overview.monthly_total,
        yearly_total=overview.yearly_total,
        next_30_days_count=overview.next_30_days_count,
        next_30_days_total=overview.next_30_days_total,
        base_currency=overview.base_currency,
        upcoming=[
            UpcomingPaymentRow(
                subscription_key=item.subscription_key,
                display_name=item.display_name,
                due_date=item.due_date,
                amount=item.amount,
                currency=item.currency,
                amount_base=item.amount_base,
                base_currency=item.base_currency,
                status=item.status,
            )
            for item in overview.upcoming
        ],
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


@router.get("/overview", response_model=SubscriptionOverviewResponse)
def get_subscription_overview(
    session: Session = Depends(get_session),
) -> SubscriptionOverviewResponse:
    return _overview_response(subscription_overview(session))


@router.post("/preference", response_model=PreferenceResponse)
def save_subscription_preference(
    req: SubscriptionPreferenceRequest,
    session: Session = Depends(get_session),
) -> PreferenceResponse:
    pref = upsert_subscription_preference(
        session,
        subscription_key=req.subscription_key,
        action=req.action,
        display_name=req.display_name,
        cadence_override=req.cadence_override,
    )
    return PreferenceResponse(id=pref.id)


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
