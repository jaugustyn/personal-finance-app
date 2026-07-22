"""Pydantic schemas for planned fixed charges."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from apps.api.schemas.transactions import ManualTransactionWrite

FixedChargeCadence = Literal["monthly", "quarterly", "semiannual", "yearly"]


class FixedChargeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    cadence: FixedChargeCadence
    anchor_date: date
    category: str | None = Field(default=None, max_length=64)


class FixedChargeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    cadence: FixedChargeCadence | None = None
    anchor_date: date | None = None
    category: str | None = Field(default=None, max_length=64)
    active: bool | None = None


class FixedChargeRow(BaseModel):
    id: int
    name: str
    amount: float
    currency: Literal["PLN"] = "PLN"
    cadence: FixedChargeCadence
    anchor_date: date
    category: str | None
    active: bool
    next_due_date: date | None
    current_due_date: date | None
    payment_status: Literal["pending", "paid", "overdue", "paused"]
    current_paid_amount: float
    linked_transaction_count: int
    last_payment_date: date | None
    monthly_equivalent: float
    yearly_cost: float


class FixedChargeSummaryRow(BaseModel):
    active_count: int
    monthly_total: float
    yearly_total: float
    next_30_days_count: int
    next_30_days_total: float
    base_currency: Literal["PLN"] = "PLN"


class FixedChargeListResponse(BaseModel):
    items: list[FixedChargeRow]
    summary: FixedChargeSummaryRow


class FixedChargeTransactionRow(BaseModel):
    transaction_id: int
    scheduled_due_date: date | None
    booking_date: date
    merchant: str
    title: str
    amount: float
    currency: str
    amount_base: float
    base_currency: Literal["PLN"] = "PLN"


class FixedChargeTransactionsResponse(BaseModel):
    fixed_charge_id: int
    current_due_date: date
    linked: list[FixedChargeTransactionRow]
    candidates: list[FixedChargeTransactionRow]


class FixedChargeLinkRequest(BaseModel):
    transaction_ids: list[int] = Field(min_length=1, max_length=20)
    scheduled_due_date: date


class FixedChargeLinkResponse(BaseModel):
    status: Literal["saved"] = "saved"


class FixedChargeManualPaymentCreate(ManualTransactionWrite):
    scheduled_due_date: date
