"""Asset quote refresh and snapshot history services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance import assets as asset_quotes
from finance.domain.models import Asset, AssetSnapshot


@dataclass(frozen=True)
class RefreshResult:
    refreshed: int
    skipped: int
    total: int


def latest_snapshot(session: Session, asset_id: int) -> AssetSnapshot | None:
    stmt = (
        select(AssetSnapshot)
        .where(AssetSnapshot.asset_id == asset_id)
        .order_by(AssetSnapshot.snapshot_date.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def refresh_one(session: Session, asset: Asset) -> AssetSnapshot | None:
    quote = asset_quotes.fetch_quote(asset.symbol)
    if quote is None:
        return None
    value_pln = asset_quotes.value_in_pln(quote.price, asset.quantity, quote.currency)
    today = date.today()
    snap = session.execute(
        select(AssetSnapshot).where(
            AssetSnapshot.asset_id == asset.id,
            AssetSnapshot.snapshot_date == today,
        )
    ).scalar_one_or_none()
    if snap is None:
        snap = AssetSnapshot(
            asset_id=asset.id,
            snapshot_date=today,
            price=quote.price,
            value_pln=value_pln,
            source="yfinance",
        )
        session.add(snap)
    else:
        snap.price = quote.price
        snap.value_pln = value_pln
    if quote.currency and asset.currency != quote.currency:
        asset.currency = quote.currency
    session.commit()
    session.refresh(snap)
    return snap


def refresh_all(session: Session) -> RefreshResult:
    assets = session.execute(select(Asset)).scalars().all()
    refreshed = 0
    skipped = 0
    for asset in assets:
        snap = refresh_one(session, asset)
        if snap is None:
            skipped += 1
        else:
            refreshed += 1
    return RefreshResult(refreshed=refreshed, skipped=skipped, total=len(assets))


def history(session: Session, *, days: int) -> list[tuple[date, Decimal]]:
    since = date.today() - timedelta(days=days)
    stmt = (
        select(AssetSnapshot.snapshot_date, func.sum(AssetSnapshot.value_pln))
        .where(AssetSnapshot.snapshot_date >= since)
        .group_by(AssetSnapshot.snapshot_date)
        .order_by(AssetSnapshot.snapshot_date)
    )
    rows = session.execute(stmt).all()
    return [(snapshot_date, Decimal(value or 0)) for snapshot_date, value in rows]
