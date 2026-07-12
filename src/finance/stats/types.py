"""Typed DTOs for dashboard statistics."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Overview(BaseModel):
    period_from: date | None
    period_to: date | None
    total_income: Decimal
    gross_expenses: Decimal
    total_refunds: Decimal
    total_expenses: Decimal
    total_debt_payments: Decimal
    total_asset_allocations: Decimal
    net_cashflow: Decimal
    savings_rate: float
    tx_count: int
    base_currency: str
    provisional_transaction_count: int = 0


class CashflowBucket(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal
    refunds: Decimal = Decimal(0)
    debt_payments: Decimal = Decimal(0)
    asset_allocations: Decimal = Decimal(0)
    net: Decimal


class CategorySpend(BaseModel):
    category: str | None
    amount: Decimal
    share: float
    count: int


class NetWorthPoint(BaseModel):
    month: str
    balance: Decimal


class MerchantSpend(BaseModel):
    merchant: str
    merchant_display: str | None = None
    merchant_canonical_key: str | None = None
    amount: Decimal
    count: int
    category: str | None = None


class CategoryTrendPoint(BaseModel):
    month: str
    category: str
    amount: Decimal


class DistributionBucket(BaseModel):
    lower: float
    upper: float
    count: int


class SpendDistribution(BaseModel):
    buckets: list[DistributionBucket]
    count: int
    mean: float
    median: float
    p95: float
    max: float
    iqr_upper: float


def month_bucket(value: date) -> str:
    """Return a stable YYYY-MM bucket independent of SQL dialect."""
    return value.strftime("%Y-%m")
