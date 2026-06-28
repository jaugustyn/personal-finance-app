"""Subscription detector — recurring debits with stable amount + cadence."""
from .detector import Subscription, detect_subscriptions
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
    "record_subscription_feedback",
]
