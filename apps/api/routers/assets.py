"""Assets portfolio: CRUD, refresh prices, history, and Sankey flow."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found
from apps.api.schemas.assets import (
    AssetIn,
    AssetOut,
    AssetPatch,
    HistoryPoint,
    PortfolioSummary,
    RefreshResult,
    SankeyData,
    SankeyLink,
    SankeyNode,
)
from finance.assets import service as asset_service
from finance.db import get_session

router = APIRouter(prefix="/assets", tags=["assets"])
fetch_quote = asset_service.asset_quotes.fetch_quote


# --- CRUD endpoints --------------------------------------------------------


@router.get("", response_model=list[AssetOut])
def list_assets(session: Session = Depends(get_session)) -> list[AssetOut]:
    return [AssetOut(**asset.__dict__) for asset in asset_service.list_assets(session)]


@router.get("/summary", response_model=PortfolioSummary)
def summary(session: Session = Depends(get_session)) -> PortfolioSummary:
    return PortfolioSummary(**asset_service.portfolio_summary(session).__dict__)


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(payload: AssetIn, session: Session = Depends(get_session)) -> AssetOut:
    asset = asset_service.create_asset(
        session,
        symbol=payload.symbol,
        name=payload.name,
        asset_class=payload.asset_class,
        currency=payload.currency,
        quantity=payload.quantity,
        cost_basis=payload.cost_basis,
        notes=payload.notes,
    )
    if asset is None:
        raise conflict("Symbol already exists")
    return AssetOut(**asset_service.to_asset_view(session, asset).__dict__)


@router.patch("/{asset_id}", response_model=AssetOut)
def patch_asset(
    asset_id: int,
    payload: AssetPatch,
    session: Session = Depends(get_session),
) -> AssetOut:
    asset = asset_service.patch_asset(
        session,
        asset_id,
        payload.model_dump(exclude_unset=True),
    )
    if asset is None:
        raise not_found("Asset not found")
    return AssetOut(**asset_service.to_asset_view(session, asset).__dict__)


@router.delete("/{asset_id}", status_code=204, response_model=None)
def delete_asset(asset_id: int, session: Session = Depends(get_session)) -> None:
    if not asset_service.delete_asset(session, asset_id):
        raise not_found("Asset not found")


@router.post("/refresh", response_model=RefreshResult)
def refresh_all(session: Session = Depends(get_session)) -> RefreshResult:
    return RefreshResult(**asset_service.refresh_all(session).__dict__)


@router.get("/history", response_model=list[HistoryPoint])
def history(
    session: Session = Depends(get_session),
    days: int = Query(default=180, ge=7, le=3650),
) -> list[HistoryPoint]:
    return [
        HistoryPoint(snapshot_date=snapshot_date, value_pln=value)
        for snapshot_date, value in asset_service.history(session, days=days)
    ]


# --- Sankey: income -> categories -> merchants ----------------------------


@router.get("/sankey", response_model=SankeyData)
def sankey(
    session: Session = Depends(get_session),
    months: int = Query(default=3, ge=1, le=36),
    top_categories: int = Query(default=8, ge=1, le=30),
    top_merchants_per_cat: int = Query(default=4, ge=1, le=20),
) -> SankeyData:
    nodes, links = asset_service.sankey(
        session,
        months=months,
        top_categories=top_categories,
        top_merchants_per_cat=top_merchants_per_cat,
    )
    return SankeyData(
        nodes=[
            SankeyNode(
                name=str(node.get("name") or ""),
                node_type=node.get("node_type"),
                category=node.get("category"),
                merchant_display=node.get("merchant_display"),
                merchant_canonical_key=node.get("merchant_canonical_key"),
            )
            for node in nodes
        ],
        links=[
            SankeyLink(
                source=int(link["source"]),
                target=int(link["target"]),
                value=Decimal(link["value"]),
            )
            for link in links
        ],
    )
