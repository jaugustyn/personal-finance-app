"""Pydantic schemas for asset API endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AssetIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = ""
    asset_class: str = "equity"
    currency: str = "USD"
    quantity: Decimal = Decimal("0")
    cost_basis: Decimal = Decimal("0")
    notes: str | None = None


class AssetPatch(BaseModel):
    name: str | None = None
    asset_class: str | None = None
    currency: str | None = None
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    notes: str | None = None


class AssetOut(BaseModel):
    id: int
    symbol: str
    name: str
    asset_class: str
    currency: str
    quantity: Decimal
    cost_basis: Decimal
    notes: str | None
    last_price: Decimal | None
    last_value_pln: Decimal | None
    last_snapshot_date: date | None
    pnl_pln: Decimal | None


class PortfolioSummary(BaseModel):
    total_value_pln: Decimal
    total_cost_pln: Decimal
    pnl_pln: Decimal
    pnl_pct: float
    asset_count: int
    last_refresh: date | None


class HistoryPoint(BaseModel):
    snapshot_date: date
    value_pln: Decimal


class SankeyNode(BaseModel):
    name: str


class SankeyLink(BaseModel):
    source: int
    target: int
    value: Decimal


class SankeyData(BaseModel):
    nodes: list[SankeyNode]
    links: list[SankeyLink]


class RefreshResult(BaseModel):
    refreshed: int
    skipped: int
    total: int
