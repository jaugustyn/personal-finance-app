"""Read models exposed by the asset tracking domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class AssetValueView:
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


@dataclass(frozen=True)
class AssetItemView:
    id: int
    account_id: int
    name: str
    asset_type: str
    currency: str
    symbol: str | None
    isin: str | None
    review_interval_days: int | None
    notes: str | None
    archived_at: datetime | None
    current_value: AssetValueView


@dataclass(frozen=True)
class AssetAccountView:
    id: int
    name: str
    institution: str | None
    kind: str
    wrapper: str
    tracking_mode: str
    default_currency: str
    notes: str | None
    archived_at: datetime | None
    amount_pln: Decimal
    native_value: Decimal | None
    native_currency: str | None
    valuation_item_id: int | None
    valuation_date: date | None
    projected: bool
    aggregate_asset_type: str | None
    review_interval_days: int | None
    stale_count: int
    matured_count: int
    unconverted_count: int
    missing_valuation_count: int
    items: list[AssetItemView]


@dataclass(frozen=True)
class AssetBreakdownView:
    asset_type: str
    amount_pln: Decimal
    share: Decimal


@dataclass(frozen=True)
class AssetOverviewView:
    as_of: date
    base_currency: str
    total_pln: Decimal
    account_count: int
    item_count: int
    stale_count: int
    matured_count: int
    unconverted_count: int
    missing_valuation_count: int
    breakdown: list[AssetBreakdownView]


@dataclass(frozen=True)
class AssetHistoryPointView:
    date: date
    amount_pln: Decimal
    unconverted_count: int


@dataclass(frozen=True)
class AssetHistoryView:
    range: str
    base_currency: str
    points: list[AssetHistoryPointView]


@dataclass(frozen=True)
class AssetFxRecomputeResult:
    updated: int
    missing: int
