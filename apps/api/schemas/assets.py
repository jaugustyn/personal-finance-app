"""Pydantic contracts for approximate asset tracking."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AccountKind = Literal["bank", "brokerage", "retirement", "crypto", "physical", "other"]
AccountWrapper = Literal["standard", "ike", "ikze", "ppk"]
TrackingMode = Literal["aggregate", "detailed"]
AssetType = Literal[
    "cash",
    "savings_account",
    "deposit",
    "bond",
    "stock",
    "etf",
    "fund",
    "crypto",
    "precious_metal",
    "loan_receivable",
    "other",
]
InputMode = Literal["total", "unit_price"]
GrowthMode = Literal["none", "fixed_rate"]
CompoundingMode = Literal["simple", "daily", "monthly", "yearly"]
HistoryRange = Literal["3m", "1y", "all"]


class AssetValuationWrite(BaseModel):
    valuation_date: date
    input_mode: InputMode = "total"
    total_value: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    growth_mode: GrowthMode = "none"
    annual_rate_percent: Decimal | None = Field(
        default=None, gt=Decimal("-100"), le=Decimal("1000")
    )
    compounding: CompoundingMode | None = None
    growth_end_date: date | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_modes(self) -> AssetValuationWrite:
        if self.input_mode == "total":
            if self.total_value is None:
                raise ValueError("total_value is required in total mode")
            if self.quantity is not None or self.unit_price is not None:
                raise ValueError("quantity and unit_price require unit_price mode")
        elif self.quantity is None or self.unit_price is None:
            raise ValueError("quantity and unit_price are required")
        if self.growth_mode == "none":
            if any(
                value is not None
                for value in (
                    self.annual_rate_percent,
                    self.compounding,
                    self.growth_end_date,
                )
            ):
                raise ValueError("growth settings require fixed_rate mode")
        elif self.annual_rate_percent is None or self.compounding is None:
            raise ValueError("annual_rate_percent and compounding are required")
        if self.growth_end_date and self.growth_end_date < self.valuation_date:
            raise ValueError("growth_end_date cannot precede valuation_date")
        return self


class AssetValuationUpdate(BaseModel):
    valuation_date: date | None = None
    input_mode: InputMode | None = None
    total_value: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    growth_mode: GrowthMode | None = None
    annual_rate_percent: Decimal | None = Field(
        default=None, gt=Decimal("-100"), le=Decimal("1000")
    )
    compounding: CompoundingMode | None = None
    growth_end_date: date | None = None

    model_config = {"extra": "forbid"}


class AssetAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    institution: str | None = Field(default=None, max_length=128)
    kind: AccountKind
    wrapper: AccountWrapper = "standard"
    tracking_mode: TrackingMode
    default_currency: str = Field(default="PLN", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=1024)
    aggregate_asset_type: AssetType | None = None
    review_interval_days: Literal[7, 30, 90, 180] | None = 30
    initial_valuation: AssetValuationWrite | None = None

    model_config = {"extra": "forbid"}


class AssetAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    institution: str | None = Field(default=None, max_length=128)
    kind: AccountKind | None = None
    wrapper: AccountWrapper | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=1024)
    aggregate_asset_type: AssetType | None = None
    review_interval_days: Literal[7, 30, 90, 180] | None = None

    model_config = {"extra": "forbid"}


class AssetItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    asset_type: AssetType
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    symbol: str | None = Field(default=None, max_length=32)
    isin: str | None = Field(default=None, max_length=12)
    review_interval_days: Literal[7, 30, 90, 180] | None = 30
    notes: str | None = Field(default=None, max_length=1024)
    initial_valuation: AssetValuationWrite | None = None

    model_config = {"extra": "forbid"}


class AssetItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    asset_type: AssetType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    symbol: str | None = Field(default=None, max_length=32)
    isin: str | None = Field(default=None, max_length=12)
    review_interval_days: Literal[7, 30, 90, 180] | None = None
    notes: str | None = Field(default=None, max_length=1024)

    model_config = {"extra": "forbid"}


class AssetValuationRow(BaseModel):
    id: int
    item_id: int
    valuation_date: date
    input_mode: InputMode
    total_value: Decimal
    quantity: Decimal | None
    unit_price: Decimal | None
    currency: str
    amount_pln: Decimal | None
    fx_rate: Decimal | None
    fx_rate_date: date | None
    fx_rate_source: str | None
    growth_mode: GrowthMode
    annual_rate_percent: Decimal | None
    compounding: CompoundingMode | None
    growth_end_date: date | None
    source: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssetValueRow(BaseModel):
    as_of: date
    valuation_id: int | None
    valuation_date: date | None
    native_value: Decimal | None
    currency: str
    amount_pln: Decimal | None
    growth_mode: str | None
    projected: bool
    stale: bool
    matured: bool
    unconverted: bool
    fx_rate_date: date | None
    fx_rate_source: str | None

    model_config = {"from_attributes": True}


class AssetItemRow(BaseModel):
    id: int
    account_id: int
    name: str
    asset_type: AssetType
    currency: str
    symbol: str | None
    isin: str | None
    review_interval_days: int | None
    notes: str | None
    archived_at: datetime | None
    current_value: AssetValueRow

    model_config = {"from_attributes": True}


class AssetAccountRow(BaseModel):
    id: int
    name: str
    institution: str | None
    kind: AccountKind
    wrapper: AccountWrapper
    tracking_mode: TrackingMode
    default_currency: str
    notes: str | None
    archived_at: datetime | None
    amount_pln: Decimal
    native_value: Decimal | None
    native_currency: str | None
    valuation_item_id: int | None
    valuation_date: date | None
    projected: bool
    aggregate_asset_type: AssetType | None
    review_interval_days: int | None
    stale_count: int
    matured_count: int
    unconverted_count: int
    missing_valuation_count: int
    items: list[AssetItemRow]

    model_config = {"from_attributes": True}


class AssetBreakdownRow(BaseModel):
    asset_type: AssetType
    amount_pln: Decimal
    share: Decimal

    model_config = {"from_attributes": True}


class AssetOverviewRow(BaseModel):
    as_of: date
    base_currency: Literal["PLN"]
    total_pln: Decimal
    account_count: int
    item_count: int
    stale_count: int
    matured_count: int
    unconverted_count: int
    missing_valuation_count: int
    breakdown: list[AssetBreakdownRow]

    model_config = {"from_attributes": True}


class AssetHistoryPointRow(BaseModel):
    date: date
    amount_pln: Decimal
    unconverted_count: int

    model_config = {"from_attributes": True}


class AssetHistoryRow(BaseModel):
    range: HistoryRange
    base_currency: Literal["PLN"]
    points: list[AssetHistoryPointRow]

    model_config = {"from_attributes": True}


class AssetMutationStatus(BaseModel):
    status: Literal["saved"] = "saved"


class AssetFxRecomputeRow(BaseModel):
    updated: int
    missing: int

    model_config = {"from_attributes": True}
