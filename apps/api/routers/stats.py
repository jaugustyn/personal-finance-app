"""Aggregated statistics for dashboards (KPI cards, cash flow, breakdowns)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import validation_error
from apps.api.schemas.stats import (
    AttentionSummary,
    CashflowBucket,
    CategorySpend,
    CategoryTrendPoint,
    CumulativeCashflowPoint,
    MerchantSort,
    MerchantSpend,
    Overview,
    Recap,
    RecapPeriod,
    SpendDistribution,
)
from finance.attention import attention_summary as build_attention_summary
from finance.db import get_session
from finance.domain.enums import TransactionDirection
from finance.stats import service as stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


# --- Endpoints -------------------------------------------------------------


@router.get("/attention-summary", response_model=AttentionSummary)
def attention_summary(session: Session = Depends(get_session)) -> AttentionSummary:
    summary = build_attention_summary(session)
    return AttentionSummary(
        transaction_reviews=summary.transaction_reviews,
        transaction_category_reviews=summary.transaction_category_reviews,
        transaction_type_reviews=summary.transaction_type_reviews,
        anomaly_reviews=summary.anomaly_reviews,
        subscription_reviews=summary.subscription_reviews,
        asset_reviews=summary.asset_reviews,
    )


@router.get("/overview", response_model=Overview)
def overview(
    session: Session = Depends(get_session),
    months: int = Query(default=1, ge=1, le=120),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> Overview:
    return stats_service.overview(
        session,
        months=None if all_data else months,
        include_transfers=include_transfers,
    )


@router.get("/cashflow", response_model=list[CashflowBucket])
def cashflow(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CashflowBucket]:
    return stats_service.cashflow(
        session,
        months=None if all_data else months,
        include_transfers=include_transfers,
    )


@router.get("/by-category", response_model=list[CategorySpend])
def by_category(
    session: Session = Depends(get_session),
    months: int = Query(default=3, ge=1, le=120),
    direction: TransactionDirection = Query(default=TransactionDirection.DEBIT),
    limit: int = Query(default=20, ge=1, le=100),
    include_transfers: bool = Query(default=False),
    include_predictions: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CategorySpend]:
    return stats_service.by_category(
        session,
        months=None if all_data else months,
        direction=direction.value,
        limit=limit,
        include_transfers=include_transfers,
        include_predictions=include_predictions,
    )


@router.get("/by-transaction-type", response_model=list[CategorySpend])
def by_transaction_type(
    session: Session = Depends(get_session),
    months: int = Query(default=3, ge=1, le=120),
    direction: TransactionDirection = Query(default=TransactionDirection.CREDIT),
    limit: int = Query(default=20, ge=1, le=100),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CategorySpend]:
    return stats_service.by_transaction_type(
        session,
        months=None if all_data else months,
        direction=direction.value,
        limit=limit,
        include_transfers=include_transfers,
    )


@router.get("/cumulative-cashflow", response_model=list[CumulativeCashflowPoint])
def cumulative_cashflow(
    session: Session = Depends(get_session),
    months: int = Query(default=24, ge=1, le=120),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CumulativeCashflowPoint]:
    """Return cumulative net cash flow for the selected period."""
    return stats_service.cumulative_cashflow(
        session,
        months=None if all_data else months,
        include_transfers=include_transfers,
    )


@router.get("/top-merchants", response_model=list[MerchantSpend])
def top_merchants(
    session: Session = Depends(get_session),
    months: int = Query(default=3, ge=1, le=120),
    limit: int = Query(default=10, ge=1, le=50),
    direction: TransactionDirection = Query(default=TransactionDirection.DEBIT),
    include_transfers: bool = Query(default=False),
    sort: MerchantSort = Query(default="amount"),
    all_data: bool = Query(default=False),
) -> list[MerchantSpend]:
    return stats_service.top_merchants(
        session,
        months=None if all_data else months,
        limit=limit,
        direction=direction.value,
        include_transfers=include_transfers,
        sort=sort,
    )


@router.get("/category-trend", response_model=list[CategoryTrendPoint])
def category_trend(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    direction: TransactionDirection = Query(default=TransactionDirection.DEBIT),
    limit: int = Query(default=5, ge=1, le=12),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> list[CategoryTrendPoint]:
    """Monthly spend per category for the top ``limit`` categories."""
    return stats_service.category_trend(
        session,
        months=None if all_data else months,
        direction=direction.value,
        limit=limit,
        include_transfers=include_transfers,
    )


@router.get("/spend-distribution", response_model=SpendDistribution)
def spend_distribution(
    session: Session = Depends(get_session),
    months: int = Query(default=12, ge=1, le=60),
    direction: TransactionDirection = Query(default=TransactionDirection.DEBIT),
    bins: int = Query(default=12, ge=4, le=40),
    include_transfers: bool = Query(default=False),
    all_data: bool = Query(default=False),
) -> SpendDistribution:
    """Histogram + summary statistics of single-transaction amounts."""
    return stats_service.spend_distribution(
        session,
        months=None if all_data else months,
        direction=direction.value,
        bins=bins,
        include_transfers=include_transfers,
    )


@router.get("/recap", response_model=Recap)
def recap(
    session: Session = Depends(get_session),
    period: RecapPeriod = Query(default="month"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    top_merchants: int = Query(default=5, ge=1, le=20),
    top_changes: int = Query(default=5, ge=1, le=20),
) -> Recap:
    """Recap of a period vs the previous one. Use date_from+date_to for a custom range."""
    if (date_from is None) != (date_to is None):
        raise validation_error("date_from and date_to must be provided together.")
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            raise validation_error("date_from must not be later than date_to.")
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
