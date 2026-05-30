"""Aggregated statistics for dashboards (KPI cards, cash flow, breakdowns)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.stats import service as stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


# --- Schemas ---------------------------------------------------------------


class Overview(BaseModel):
    period_from: date | None
    period_to: date | None
    total_income: Decimal
    total_expenses: Decimal
    net_cashflow: Decimal
    savings_rate: float  # 0..1, fraction of income saved
    tx_count: int


class CashflowBucket(BaseModel):
    month: str  # YYYY-MM
    income: Decimal
    expenses: Decimal
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
    amount: Decimal
    count: int


# --- Endpoints -------------------------------------------------------------


@router.get("/overview", response_model=Overview)
def overview(
    session: Session = Depends(get_session),
    months: int = Query(default=1, ge=1, le=120),
    include_transfers: bool = Query(default=False),
) -> Overview:
    return Overview(
        **stats_service.overview(
            session,
            months=months,
            include_transfers=include_transfers,
        )
    )


@router.get("/cashflow", response_model=list[CashflowBucket])
def cashflow(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    include_transfers: bool = Query(default=False),
) -> list[CashflowBucket]:
    return [
        CashflowBucket(**row)
        for row in stats_service.cashflow(
            session,
            months=months,
            include_transfers=include_transfers,
        )
    ]


@router.get("/by-category", response_model=list[CategorySpend])
def by_category(
    session: Session = Depends(get_session),
    months: int = Query(default=3, ge=1, le=120),
    direction: str = Query(default="debit", pattern="^(debit|credit)$"),
    limit: int = Query(default=20, ge=1, le=100),
    include_transfers: bool = Query(default=False),
    include_predictions: bool = Query(default=False),
) -> list[CategorySpend]:
    return [
        CategorySpend(**row)
        for row in stats_service.by_category(
            session,
            months=months,
            direction=direction,
            limit=limit,
            include_transfers=include_transfers,
            include_predictions=include_predictions,
        )
    ]


@router.get("/networth", response_model=list[NetWorthPoint])
def networth(
    session: Session = Depends(get_session),
    months: int = Query(default=24, ge=1, le=120),
    include_transfers: bool = Query(default=False),
) -> list[NetWorthPoint]:
    """Cumulative net cashflow over time (proxy for savings balance)."""
    return [
        NetWorthPoint(**row)
        for row in stats_service.networth(
            session,
            months=months,
            include_transfers=include_transfers,
        )
    ]


@router.get("/top-merchants", response_model=list[MerchantSpend])
def top_merchants(
    session: Session = Depends(get_session),
    months: int = Query(default=3, ge=1, le=120),
    limit: int = Query(default=10, ge=1, le=50),
    direction: str = Query(default="debit", pattern="^(debit|credit)$"),
    include_transfers: bool = Query(default=False),
) -> list[MerchantSpend]:
    return [
        MerchantSpend(**row)
        for row in stats_service.top_merchants(
            session,
            months=months,
            limit=limit,
            direction=direction,
            include_transfers=include_transfers,
        )
    ]

