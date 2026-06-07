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
    category: str | None = None


class CategoryTrendPoint(BaseModel):
    month: str  # YYYY-MM
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
    iqr_upper: float  # Tukey upper fence (Q3 + 1.5*IQR) for outlier flagging


class RecapCashflow(BaseModel):
    income: Decimal
    expenses: Decimal
    net: Decimal
    income_delta: Decimal
    expenses_delta: Decimal
    net_delta: Decimal


class RecapCategoryChange(BaseModel):
    category: str
    current: Decimal
    previous: Decimal
    delta: Decimal


class RecapMerchant(BaseModel):
    merchant: str
    amount: Decimal
    count: int


class RecapLimitBreach(BaseModel):
    category: str
    spent: Decimal
    limit: Decimal
    overshoot: Decimal


class RecapSavings(BaseModel):
    goal: Decimal
    net: Decimal
    ratio: float
    met: bool


class Recap(BaseModel):
    period: str  # "week" | "month"
    current_from: date
    current_to: date
    previous_from: date
    previous_to: date
    cashflow: RecapCashflow
    category_changes: list[RecapCategoryChange]
    top_merchants: list[RecapMerchant]
    limit_breaches: list[RecapLimitBreach]
    savings_progress: RecapSavings | None


# --- Endpoints -------------------------------------------------------------


@router.get("/overview", response_model=Overview)
def overview(
    session: Session = Depends(get_session),
    months: int = Query(default=1, ge=1, le=120),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> Overview:
    return Overview(
        **stats_service.overview(
            session,
            months=None if all_data else months,
            include_transfers=include_transfers,
        )
    )


@router.get("/cashflow", response_model=list[CashflowBucket])
def cashflow(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CashflowBucket]:
    return [
        CashflowBucket(**row)
        for row in stats_service.cashflow(
            session,
            months=None if all_data else months,
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
    all_data: bool = Query(default=False),
) -> list[CategorySpend]:
    return [
        CategorySpend(**row)
        for row in stats_service.by_category(
            session,
            months=None if all_data else months,
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
    all_data: bool = Query(default=False),
) -> list[NetWorthPoint]:
    """Cumulative net cashflow over time (proxy for savings balance)."""
    return [
        NetWorthPoint(**row)
        for row in stats_service.networth(
            session,
            months=None if all_data else months,
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
    sort: str = Query(default="amount", pattern="^(amount|count)$"),
    all_data: bool = Query(default=False),
) -> list[MerchantSpend]:
    return [
        MerchantSpend(**row)
        for row in stats_service.top_merchants(
            session,
            months=None if all_data else months,
            limit=limit,
            direction=direction,
            include_transfers=include_transfers,
            sort=sort,
        )
    ]


@router.get("/category-trend", response_model=list[CategoryTrendPoint])
def category_trend(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    direction: str = Query(default="debit", pattern="^(debit|credit)$"),
    limit: int = Query(default=5, ge=1, le=12),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CategoryTrendPoint]:
    """Monthly spend per category for the top ``limit`` categories."""
    return [
        CategoryTrendPoint(**row)
        for row in stats_service.category_trend(
            session,
            months=None if all_data else months,
            direction=direction,
            limit=limit,
            include_transfers=include_transfers,
        )
    ]


@router.get("/spend-distribution", response_model=SpendDistribution)
def spend_distribution(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    direction: str = Query(default="debit", pattern="^(debit|credit)$"),
    bins: int = Query(default=12, ge=4, le=40),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> SpendDistribution:
    """Histogram + summary statistics of single-transaction amounts."""
    return SpendDistribution(
        **stats_service.spend_distribution(
            session,
            months=None if all_data else months,
            direction=direction,
            bins=bins,
            include_transfers=include_transfers,
        )
    )


@router.get("/recap", response_model=Recap)
def recap(
    session: Session = Depends(get_session),
    period: str = Query(default="month", pattern="^(week|month)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    top_merchants: int = Query(default=5, ge=1, le=20),
    top_changes: int = Query(default=5, ge=1, le=20),
) -> Recap:
    """Recap of a period vs the previous one. Use date_from+date_to for a custom range."""
    if date_from is not None and date_to is not None and date_from <= date_to:
        return Recap(
            **stats_service.custom_recap(
                session,
                date_from=date_from,
                date_to=date_to,
                top_merchants=top_merchants,
                top_changes=top_changes,
            )
        )
    return Recap(
        **stats_service.period_recap(
            session,
            period=period,
            top_merchants=top_merchants,
            top_changes=top_changes,
        )
    )
