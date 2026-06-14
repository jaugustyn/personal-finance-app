"""Subscription detector — recurring debits with stable amount + cadence."""
from .detector import Subscription, detect_subscriptions, normalize_merchant
from .service import (
    SubscriptionReviewRow,
    list_subscription_rows,
    record_subscription_feedback,
)

__all__ = [
    "Subscription",
    "SubscriptionReviewRow",
    "detect_subscriptions",
    "list_subscription_rows",
    "normalize_merchant",
    "record_subscription_feedback",
]
