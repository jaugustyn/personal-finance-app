"""Pydantic schemas for statistics API endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from finance.stats.types import (
    CashflowBucket,
    CategorySpend,
    CategoryTrendPoint,
    CumulativeCashflowPoint,
    MerchantSpend,
    Overview,
    SpendDistribution,
)

MerchantSort = Literal["amount", "count"]
RecapPeriod = Literal["week", "month"]


class AttentionSummary(BaseModel):
    transaction_reviews: int
    transaction_category_reviews: int
    transaction_type_reviews: int
    anomaly_reviews: int
    subscription_reviews: int
    asset_reviews: int


class RecapCashflow(BaseModel):
    income: Decimal
    gross_expenses: Decimal
    refunds: Decimal
    expenses: Decimal
    debt_payments: Decimal
    asset_allocations: Decimal
    net: Decimal
    income_delta: Decimal
    gross_expenses_delta: Decimal
    refunds_delta: Decimal
    expenses_delta: Decimal
    debt_payments_delta: Decimal
    asset_allocations_delta: Decimal
    net_delta: Decimal


class RecapCategoryChange(BaseModel):
    category: str
    current: Decimal
    previous: Decimal
    delta: Decimal
    current_count: int
    previous_count: int
    change_percent: float | None


class RecapMerchantChange(BaseModel):
    merchant: str
    merchant_display: str | None = None
    merchant_canonical_key: str | None = None
    current: Decimal
    previous: Decimal
    delta: Decimal
    current_count: int
    previous_count: int
    change_percent: float | None


class Recap(BaseModel):
    period: str
    base_currency: str
    current_from: date
    current_to: date
    previous_from: date
    previous_to: date
    cashflow: RecapCashflow
    category_changes: list[RecapCategoryChange]
    merchant_changes: list[RecapMerchantChange]
    unconverted_count: int


__all__ = [
    "AttentionSummary",
    "CashflowBucket",
    "CategorySpend",
    "CategoryTrendPoint",
    "MerchantSort",
    "MerchantSpend",
    "CumulativeCashflowPoint",
    "Overview",
    "Recap",
    "RecapPeriod",
    "SpendDistribution",
]
