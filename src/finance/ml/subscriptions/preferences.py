"""Subscription preference and feedback mutations."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.models import MlFeedbackEvent, SubscriptionPreference
from finance.ml.feedback import (
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SUBSCRIPTION_REJECTED,
    EVENT_SUBSCRIPTION_RESTORED,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.ml.subscriptions.detector import normalize_subscription_merchant
from finance.ml.subscriptions.projection import subscription_key as make_subscription_key
from finance.ml.subscriptions.repository import transaction_frame
from finance.ml.subscriptions.types import (
    SubscriptionFeedbackAction,
    SubscriptionPreferenceAction,
)
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_identity,
    merchant_key,
)


def upsert_subscription_preference(
    session: Session,
    *,
    subscription_key: str,
    action: SubscriptionPreferenceAction = "update",
    display_name: str | None = None,
    cadence_override: str | None = None,
) -> SubscriptionPreference:
    pref = session.execute(
        select(SubscriptionPreference).where(
            SubscriptionPreference.subscription_key == subscription_key
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = SubscriptionPreference(subscription_key=subscription_key)
        session.add(pref)
    if display_name is not None:
        pref.display_name = display_name.strip() or None
    if cadence_override is not None:
        pref.cadence_override = cadence_override or None
    if action == "confirm":
        pref.confirmed = True
    elif action == "reject":
        pref.confirmed = False
        record_feedback_event(
            session,
            FeedbackEventInput(
                event_type=EVENT_SUBSCRIPTION_REJECTED,
                entity_type="subscription_merchant",
                entity_key=subscription_key,
                source="subscription_management",
            ),
        )
    elif action == "restore":
        pref.confirmed = False
        record_feedback_event(
            session,
            FeedbackEventInput(
                event_type=EVENT_SUBSCRIPTION_RESTORED,
                entity_type="subscription_merchant",
                entity_key=subscription_key,
                source="subscription_management",
            ),
        )
    elif action == "update":
        pass
    session.commit()
    session.refresh(pref)
    return pref


def record_subscription_feedback(
    session: Session,
    *,
    merchant: str,
    action: SubscriptionFeedbackAction,
    subscription_key: str | None = None,
) -> MlFeedbackEvent:
    normalized = normalize_subscription_merchant(merchant)
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=EVENT_SUBSCRIPTION_CONFIRMED,
            entity_type="subscription_merchant",
            entity_key=subscription_key or normalized,
            source="subscription_detector",
        ),
    )
    if action == "confirm":
        keys = {subscription_key} if subscription_key else set()
        if not keys:
            alias_map, label_map = load_merchant_alias_maps(session)
            identity = merchant_identity(merchant, alias_map=alias_map, label_map=label_map)
            candidate_keys = {
                value
                for value in {
                    normalized,
                    identity.canonical_key,
                    merchant_key(merchant),
                }
                if value
            }
            df = transaction_frame(session)
            if not df.empty and candidate_keys:
                display_keys = df["merchant_display"].fillna("").astype(str).map(
                    normalize_subscription_merchant
                )
                matches = df[
                    df["merchant_norm"].isin(candidate_keys)
                    | display_keys.isin(candidate_keys)
                ]
                for row in matches.itertuples():
                    keys.add(make_subscription_key(str(row.merchant_norm), str(row.currency or "")))
            if not keys:
                keys.add(normalized)
        for key in keys:
            upsert_subscription_preference(
                session,
                subscription_key=key,
                action="confirm",
                display_name=merchant,
            )
    session.commit()
    session.refresh(event)
    return event
