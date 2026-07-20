"""Database reads for subscription review workflows."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.currencies import BASE_CURRENCY, amount_base_value
from finance.domain.models import MlFeedbackEvent, SubscriptionPreference, Transaction
from finance.ml.feedback import (
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SUBSCRIPTION_REJECTED,
    EVENT_SUBSCRIPTION_RESTORED,
)
from finance.ml.subscriptions.detector import normalize_subscription_merchant
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)
from finance.transactions.type_decision import effective_transaction_type


def transaction_frame(session: Session) -> pd.DataFrame:
    rows = session.execute(select(Transaction)).scalars().all()
    alias_map, label_map = load_merchant_alias_maps(session)
    items = []
    for row in rows:
        base_amount = amount_base_value(row)
        if base_amount is None:
            continue
        identity = merchant_identity(
            row.merchant,
            row.title,
            alias_map=alias_map,
            label_map=label_map,
        )
        merchant_norm = identity.canonical_key or normalize_subscription_merchant(
            row.merchant,
            row.title,
        )
        merchant_display = identity.display_label or merchant_display_label(
            row.merchant,
            row.title,
        )
        items.append(
            {
                "booking_date": row.booking_date,
                "transaction_id": row.id,
                "amount": float(row.amount),
                "amount_base": float(base_amount),
                "direction": row.direction,
                "merchant": row.merchant or "",
                "title": row.title or "",
                "merchant_norm": merchant_norm,
                "merchant_display": merchant_display,
                "currency": row.currency or "",
                "base_currency": BASE_CURRENCY,
                "category": row.category,
                "category_source": row.category_source,
                "is_transfer": row.is_transfer,
                "transaction_type": effective_transaction_type(row),
            }
        )
    return pd.DataFrame(items)


def load_preferences(session: Session) -> dict[str, SubscriptionPreference]:
    prefs = session.execute(select(SubscriptionPreference)).scalars().all()
    return {pref.subscription_key: pref for pref in prefs}


def subscription_feedback_decisions(session: Session) -> dict[str, str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key, MlFeedbackEvent.event_type).where(
            MlFeedbackEvent.event_type.in_(
                [
                    EVENT_SUBSCRIPTION_CONFIRMED,
                    EVENT_SUBSCRIPTION_REJECTED,
                    EVENT_SUBSCRIPTION_RESTORED,
                ]
            ),
            MlFeedbackEvent.entity_type == "subscription_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        ).order_by(MlFeedbackEvent.created_at.asc(), MlFeedbackEvent.id.asc())
    ).all()
    return {str(key): str(event_type) for key, event_type in rows if key}
