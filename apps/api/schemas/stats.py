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
    MerchantSpend,
    NetWorthPoint,
    Overview,
    SpendDistribution,
)

MerchantSort = Literal["amount", "count"]
RecapPeriod = Literal["week", "month"]


class RecapCashflow(BaseModel):
    income: Decimal
    expenses: Decimal
    net: Decimal
    income_delta: Decimal
    expenses_delta: Decimal
    net_delta: Decimal


class RecapCategoryChange(BaseModel):
    category: str
    current: Decimal
    previous: Decimal
    delta: Decimal


class RecapMerchant(BaseModel):
    merchant: str
    amount: Decimal
    count: int


class RecapLimitBreach(BaseModel):
    category: str
    spent: Decimal
    limit: Decimal
    overshoot: Decimal


class RecapSavings(BaseModel):
    goal: Decimal
    net: Decimal
    ratio: float
    met: bool


class Recap(BaseModel):
    period: str
    current_from: date
    current_to: date
    previous_from: date
    previous_to: date
    cashflow: RecapCashflow
    category_changes: list[RecapCategoryChange]
    top_merchants: list[RecapMerchant]
    limit_breaches: list[RecapLimitBreach]
    savings_progress: RecapSavings | None


__all__ = [
    "CashflowBucket",
    "CategorySpend",
    "CategoryTrendPoint",
    "MerchantSort",
    "MerchantSpend",
    "NetWorthPoint",
    "Overview",
    "Recap",
    "RecapPeriod",
    "SpendDistribution",
]
