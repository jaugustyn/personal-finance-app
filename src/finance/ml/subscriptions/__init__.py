"""Subscription detector — recurring debits with stable amount + cadence."""
from .detector import Subscription, detect_subscriptions, normalize_merchant

__all__ = ["Subscription", "detect_subscriptions", "normalize_merchant"]
