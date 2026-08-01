"""Database reads for subscription review workflows."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.currencies import BASE_CURRENCY, amount_base_expr
from finance.domain.models import MlFeedbackEvent, SubscriptionPreference, Transaction
from finance.ml.feedback import (
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SUBSCRIPTION_REJECTED,
    EVENT_SUBSCRIPTION_RESTORED,
)
from finance.ml.subscriptions.detector import normalize_subscription_merchant
from finance.transactions.merchants import (
    load_merchant_identity_resolver,
    merchant_display_label,
)
from finance.transactions.type_decision import effective_transaction_type_expr


def transaction_frame(session: Session) -> pd.DataFrame:
    base_amount = amount_base_expr()
    rows = (
        session.execute(
            select(
                Transaction.booking_date.label("booking_date"),
                Transaction.id.label("transaction_id"),
                Transaction.amount.label("amount"),
                base_amount.label("amount_base"),
                Transaction.direction.label("direction"),
                Transaction.merchant.label("merchant"),
                Transaction.title.label("title"),
                Transaction.currency.label("currency"),
                Transaction.category.label("category"),
                Transaction.category_source.label("category_source"),
                Transaction.is_transfer.label("is_transfer"),
                effective_transaction_type_expr().label("transaction_type"),
            ).where(base_amount.is_not(None))
        )
        .mappings()
        .all()
    )
    resolver = load_merchant_identity_resolver(session)
    items = []
    for row in rows:
        merchant = str(row["merchant"] or "")
        title = str(row["title"] or "")
        identity = resolver.resolve(merchant, title)
        saved_canonical_key = resolver.alias_map.get(identity.alias_key)
        merchant_norm = saved_canonical_key or normalize_subscription_merchant(
            merchant,
            title,
        )
        merchant_display = (
            resolver.label_map.get(saved_canonical_key, "")
            if saved_canonical_key
            else ""
        ) or merchant_display_label(merchant, title)
        items.append(
            {
                "booking_date": row["booking_date"],
                "transaction_id": row["transaction_id"],
                "amount": float(row["amount"]),
                "amount_base": float(row["amount_base"]),
                "direction": row["direction"],
                "merchant": merchant,
                "title": title,
                "merchant_norm": merchant_norm,
                "merchant_display": merchant_display,
                "currency": row["currency"] or "",
                "base_currency": BASE_CURRENCY,
                "category": row["category"],
                "category_source": row["category_source"],
                "is_transfer": row["is_transfer"],
                "transaction_type": row["transaction_type"],
            }
        )
    return pd.DataFrame(items)


def load_preferences(session: Session) -> dict[str, SubscriptionPreference]:
    prefs = session.execute(select(SubscriptionPreference)).scalars().all()
    return {pref.subscription_key: pref for pref in prefs}


def subscription_feedback_decisions(session: Session) -> dict[str, str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key, MlFeedbackEvent.event_type)
        .where(
            MlFeedbackEvent.event_type.in_(
                [
                    EVENT_SUBSCRIPTION_CONFIRMED,
                    EVENT_SUBSCRIPTION_REJECTED,
                    EVENT_SUBSCRIPTION_RESTORED,
                ]
            ),
            MlFeedbackEvent.entity_type == "subscription_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        )
        .order_by(MlFeedbackEvent.created_at.asc(), MlFeedbackEvent.id.asc())
    ).all()
    return {str(key): str(event_type) for key, event_type in rows if key}
