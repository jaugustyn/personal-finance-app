"""Pydantic schemas for currency API endpoints."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FxRateRow(BaseModel):
    id: int
    currency: str
    base_currency: str
    rate_date: date
    rate: Decimal
    source: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CurrencyTotals(BaseModel):
    currency: str
    count: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal


class MissingRateRow(BaseModel):
    currency: str
    base_currency: str
    rate_date: date
    count: int


class CurrencyStatus(BaseModel):
    base_currency: str
    currencies: list[CurrencyTotals]
    missing_rates: list[MissingRateRow]
    missing_rate_count: int


class FxRatePayload(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(gt=0)

    model_config = {"extra": "forbid"}


class FetchNbpResult(BaseModel):
    fetched: int
    missing: int


class RecomputeResult(BaseModel):
    updated: int
    missing: int
