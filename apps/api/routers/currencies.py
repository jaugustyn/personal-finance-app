"""Currency rates and conversion status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import validation_error
from apps.api.schemas.currencies import (
    CurrencyStatus,
    FetchNbpResult,
    FxRatePayload,
    FxRateRow,
    RecomputeResult,
)
from finance.currencies import (
    BASE_CURRENCY,
    add_manual_rate,
    fetch_nbp_rates_for_missing_transactions,
    list_rates,
    recompute_transactions,
    status,
)
from finance.db import get_session

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("/status", response_model=CurrencyStatus)
def currency_status(session: Session = Depends(get_session)) -> CurrencyStatus:
    return CurrencyStatus(**status(session))


@router.get("/rates", response_model=list[FxRateRow])
def get_rates(
    session: Session = Depends(get_session),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[FxRateRow]:
    return [
        FxRateRow.model_validate(row)
        for row in list_rates(
            session,
            currency=currency,
            limit=limit,
        )
    ]


@router.post("/rates", response_model=FxRateRow, status_code=201)
def post_rate(
    payload: FxRatePayload,
    session: Session = Depends(get_session),
) -> FxRateRow:
    try:
        row = add_manual_rate(
            session,
            currency=payload.currency,
            base_currency=BASE_CURRENCY,
            rate_date=payload.rate_date,
            rate=payload.rate,
            source="manual",
        )
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    session.commit()
    session.refresh(row)
    return FxRateRow.model_validate(row)


@router.post("/fetch-nbp", response_model=FetchNbpResult)
def fetch_nbp(session: Session = Depends(get_session)) -> FetchNbpResult:
    return FetchNbpResult(**fetch_nbp_rates_for_missing_transactions(session))


@router.post("/recompute", response_model=RecomputeResult)
def recompute(session: Session = Depends(get_session)) -> RecomputeResult:
    return RecomputeResult(**recompute_transactions(session))
