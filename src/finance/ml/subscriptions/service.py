"""Shared subscription review service used by API and LLM tools."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from finance.ml.subscriptions.detector import detect_subscriptions
from finance.ml.subscriptions.preferences import (
    record_subscription_feedback,
    upsert_subscription_preference,
)
from finance.ml.subscriptions.projection import (
    category_subscription_rows,
    detected_subscription_row,
    overview_from_rows,
    preference_only_rows,
    user_decision,
)
from finance.ml.subscriptions.repository import (
    load_preferences,
    subscription_feedback_decisions,
    transaction_frame,
)
from finance.ml.subscriptions.types import (
    SubscriptionFeedbackAction,
    SubscriptionOverview,
    SubscriptionPreferenceAction,
    SubscriptionReviewRow,
    SubscriptionTransactionSample,
    SubscriptionUpcomingPayment,
    SubscriptionUserDecision,
)

__all__ = [
    "SubscriptionFeedbackAction",
    "SubscriptionOverview",
    "SubscriptionPreferenceAction",
    "SubscriptionReviewRow",
    "SubscriptionTransactionSample",
    "SubscriptionUpcomingPayment",
    "SubscriptionUserDecision",
    "list_subscription_rows",
    "record_subscription_feedback",
    "subscription_overview",
    "upsert_subscription_preference",
]


def list_subscription_rows(
    session: Session,
    *,
    min_occurrences: int = 2,
    amount_tol: float = 0.10,
    day_tol: int = 5,
    min_confidence: float = 0.0,
    include_rejected: bool = False,
    as_of: date | None = None,
) -> list[SubscriptionReviewRow]:
    as_of = as_of or date.today()
    df = transaction_frame(session)
    if df.empty:
        return []
    preferences = load_preferences(session)
    feedback_decisions = subscription_feedback_decisions(session)

    def is_rejected(key: str) -> bool:
        return (
            user_decision(
                key,
                preferences=preferences,
                feedback_decisions=feedback_decisions,
            )
            == "rejected"
        )

    active_preferences = {
        key: pref
        for key, pref in preferences.items()
        if include_rejected or not is_rejected(key)
    }
    subs = detect_subscriptions(
        df,
        min_occurrences=min_occurrences,
        amount_tol=amount_tol,
        day_tol=day_tol,
    )
    rows: list[SubscriptionReviewRow] = []
    for sub in subs:
        pref = preferences.get(sub.merchant_key)
        rejected = is_rejected(sub.merchant_key)
        if rejected and not include_rejected:
            continue
        row = detected_subscription_row(
            sub,
            preference=pref,
            user_decision="rejected" if rejected else user_decision(
                sub.merchant_key,
                preferences=preferences,
                feedback_decisions=feedback_decisions,
            ),
            as_of=as_of,
        )
        if (
            row.source == "detected"
            and not row.is_confirmed
            and row.user_decision != "rejected"
            and row.confidence < min_confidence
        ):
            continue
        rows.append(row)
    detected_keys = {row.merchant_key for row in rows}
    rows.extend(
        row
        for row in category_subscription_rows(
            df,
            preferences=active_preferences,
            feedback_decisions=feedback_decisions,
            detected_keys=detected_keys,
            as_of=as_of,
        )
        if include_rejected or not is_rejected(row.merchant_key)
    )
    existing_keys = {row.merchant_key for row in rows}
    rows.extend(
        preference_only_rows(
            df,
            preferences=active_preferences,
            feedback_decisions=feedback_decisions,
            existing_keys=existing_keys,
            as_of=as_of,
        )
    )
    rows.sort(key=lambda row: row.estimated_monthly_cost, reverse=True)
    return rows


def subscription_overview(
    session: Session,
    *,
    as_of: date | None = None,
) -> SubscriptionOverview:
    as_of = as_of or date.today()
    rows = [
        row
        for row in list_subscription_rows(session, min_confidence=0.0, as_of=as_of)
        if row.status not in {"probably_cancelled", "paused_or_missing"}
    ]
    return overview_from_rows(rows, as_of=as_of)
