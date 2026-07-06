"""GET /subscriptions — recurring debits with stable amount + cadence."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import validation_error
from apps.api.schemas.subscriptions import (
    FeedbackResponse,
    PreferenceResponse,
    SubscriptionFeedbackRequest,
    SubscriptionOverviewResponse,
    SubscriptionPreferenceRequest,
    SubscriptionRow,
    SubscriptionTransactionRow,
    UpcomingPaymentRow,
)
from finance.db import get_session
from finance.ml.subscriptions.service import (
    SubscriptionOverview,
    SubscriptionReviewRow,
    list_subscription_rows,
    subscription_overview,
    upsert_subscription_preference,
)
from finance.ml.subscriptions.service import (
    record_subscription_feedback as record_subscription_feedback_event,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _to_response(row: SubscriptionReviewRow) -> SubscriptionRow:
    return SubscriptionRow(
        merchant=row.merchant,
        merchant_key=row.merchant_key,
        merchant_display=row.merchant_display,
        merchant_canonical_key=row.merchant_canonical_key,
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
        user_decision=row.user_decision,
        transactions=[
            SubscriptionTransactionRow(
                id=item.id,
                booking_date=item.booking_date,
                merchant=item.merchant,
                merchant_display=item.merchant_display,
                merchant_canonical_key=item.merchant_canonical_key,
                title=item.title,
                amount=item.amount,
                currency=item.currency,
                amount_base=item.amount_base,
                base_currency=item.base_currency,
                category=item.category,
                category_source=item.category_source,
            )
            for item in row.transactions
        ],
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
    include_rejected: bool = Query(default=False),
) -> list[SubscriptionRow]:
    return [
        _to_response(row)
        for row in list_subscription_rows(
            session,
            min_occurrences=min_occurrences,
            amount_tol=amount_tol,
            day_tol=day_tol,
            min_confidence=min_confidence,
            include_rejected=include_rejected,
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
    if not req.subscription_key and not req.merchant_canonical_key and not req.merchant:
        raise validation_error(
            "Provide subscription_key, merchant_canonical_key or merchant."
        )
    event = record_subscription_feedback_event(
        session,
        merchant=req.merchant,
        action=req.action,
        merchant_canonical_key=req.merchant_canonical_key,
        subscription_key=req.subscription_key,
    )
    return FeedbackResponse(id=event.id)
