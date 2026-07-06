"""Pydantic schemas for subscription API endpoints."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class SubscriptionTransactionRow(BaseModel):
    id: int
    booking_date: date
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    title: str
    amount: float
    currency: str
    amount_base: float
    base_currency: str
    category: str | None
    category_source: str | None


class SubscriptionRow(BaseModel):
    merchant: str
    merchant_key: str
    merchant_display: str
    merchant_canonical_key: str
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
    user_decision: Literal["suggested", "confirmed", "rejected"]
    transactions: list[SubscriptionTransactionRow]


class SubscriptionFeedbackRequest(BaseModel):
    merchant: str | None = None
    merchant_canonical_key: str | None = None
    action: Literal["confirm"]
    subscription_key: str | None = None


class SubscriptionPreferenceRequest(BaseModel):
    subscription_key: str
    action: Literal["confirm", "reject", "restore", "update"] = "update"
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
