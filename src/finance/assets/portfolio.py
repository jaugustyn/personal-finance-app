"""Asset CRUD and portfolio summary services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.assets.snapshots import latest_snapshot, refresh_one
from finance.domain.models import Asset


@dataclass(frozen=True)
class AssetView:
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


@dataclass(frozen=True)
class PortfolioSummary:
    total_value_pln: Decimal
    total_cost_pln: Decimal
    pnl_pln: Decimal
    pnl_pct: float
    asset_count: int
    last_refresh: date | None


def to_asset_view(session: Session, asset: Asset) -> AssetView:
    snap = latest_snapshot(session, asset.id)
    last_value = snap.value_pln if snap else None
    pnl = (last_value - asset.cost_basis) if last_value is not None else None
    return AssetView(
        id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        asset_class=asset.asset_class,
        currency=asset.currency,
        quantity=asset.quantity,
        cost_basis=asset.cost_basis,
        notes=asset.notes,
        last_price=snap.price if snap else None,
        last_value_pln=last_value,
        last_snapshot_date=snap.snapshot_date if snap else None,
        pnl_pln=pnl,
    )


def list_assets(session: Session) -> list[AssetView]:
    rows = session.execute(select(Asset).order_by(Asset.symbol)).scalars().all()
    return [to_asset_view(session, asset) for asset in rows]


def portfolio_summary(session: Session) -> PortfolioSummary:
    assets = session.execute(select(Asset)).scalars().all()
    total_value = Decimal("0")
    total_cost = Decimal("0")
    last_refresh: date | None = None
    for asset in assets:
        snap = latest_snapshot(session, asset.id)
        if snap:
            total_value += snap.value_pln
            if last_refresh is None or snap.snapshot_date > last_refresh:
                last_refresh = snap.snapshot_date
        total_cost += asset.cost_basis
    pnl = total_value - total_cost
    pct = float(pnl / total_cost) if total_cost > 0 else 0.0
    return PortfolioSummary(
        total_value_pln=total_value,
        total_cost_pln=total_cost,
        pnl_pln=pnl,
        pnl_pct=pct,
        asset_count=len(assets),
        last_refresh=last_refresh,
    )


def create_asset(
    session: Session,
    *,
    symbol: str,
    name: str,
    asset_class: str,
    currency: str,
    quantity: Decimal,
    cost_basis: Decimal,
    notes: str | None,
) -> Asset | None:
    normalized_symbol = symbol.upper()
    existing = session.execute(
        select(Asset).where(Asset.symbol == normalized_symbol)
    ).scalar_one_or_none()
    if existing is not None:
        return None
    asset = Asset(
        symbol=normalized_symbol,
        name=name or normalized_symbol,
        asset_class=asset_class,
        currency=currency.upper(),
        quantity=quantity,
        cost_basis=cost_basis,
        notes=notes,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    refresh_one(session, asset)
    return asset


def patch_asset(session: Session, asset_id: int, values: dict[str, object]) -> Asset | None:
    asset = session.get(Asset, asset_id)
    if asset is None:
        return None
    for field, value in values.items():
        setattr(asset, field, value)
    session.commit()
    session.refresh(asset)
    return asset


def delete_asset(session: Session, asset_id: int) -> bool:
    asset = session.get(Asset, asset_id)
    if asset is None:
        return False
    session.delete(asset)
    session.commit()
    return True
