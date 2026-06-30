"""Shared types for subscription review services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

SubscriptionFeedbackAction = Literal["confirm"]
SubscriptionPreferenceAction = Literal[
    "confirm",
    "reject",
    "restore",
    "update",
]
SubscriptionUserDecision = Literal["suggested", "confirmed", "rejected"]

PRICE_CHANGE_RELATIVE_THRESHOLD = 0.08
PRICE_CHANGE_ABSOLUTE_THRESHOLD = 1.0
REVIEW_CONFIDENCE_THRESHOLD = 0.65
UPCOMING_WINDOW_DAYS = 30
ANNUAL_RENEWAL_WINDOW_DAYS = 90


@dataclass(frozen=True)
class SubscriptionTransactionSample:
    id: int
    booking_date: date
    merchant: str
    title: str
    amount: float
    currency: str
    amount_base: float
    base_currency: str
    category: str | None
    category_source: str | None


@dataclass(frozen=True)
class SubscriptionReviewRow:
    merchant: str
    merchant_key: str
    currency: str
    base_currency: str
    cadence: str
    median_amount: float
    occurrences: int
    last_seen: date
    estimated_monthly_cost_original: float
    estimated_monthly_cost: float
    confidence: float
    status: str
    source: str
    next_expected_date: date | None
    previous_amount: float | None
    current_amount: float | None
    price_change_pct: float | None
    price_change_annual_impact: float | None
    evidence: dict[str, object]
    is_confirmed: bool
    user_decision: SubscriptionUserDecision
    display_name: str
    transactions: list[SubscriptionTransactionSample]


@dataclass(frozen=True)
class SubscriptionUpcomingPayment:
    subscription_key: str
    display_name: str
    due_date: date
    amount: float
    currency: str
    amount_base: float
    base_currency: str
    status: str


@dataclass(frozen=True)
class SubscriptionOverview:
    monthly_total: float
    yearly_total: float
    next_30_days_count: int
    next_30_days_total: float
    base_currency: str
    upcoming: list[SubscriptionUpcomingPayment]
