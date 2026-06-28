"""Currency rates and conversion status endpoints."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.currencies import (
    add_manual_rate,
    fetch_nbp_rates_for_missing_transactions,
    list_rates,
    recompute_transactions,
    status,
)
from finance.db import get_session

router = APIRouter(prefix="/currencies", tags=["currencies"])


class FxRateRow(BaseModel):
    id: int
    currency: str
    base_currency: str
    rate_date: date
    rate: Decimal
    source: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CurrencyTotals(BaseModel):
    currency: str
    count: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal


class MissingRateRow(BaseModel):
    currency: str
    base_currency: str
    rate_date: date
    count: int


class CurrencyStatus(BaseModel):
    base_currency: str
    currencies: list[CurrencyTotals]
    missing_rates: list[MissingRateRow]
    missing_rate_count: int


class FxRatePayload(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(gt=0)


class FetchNbpResult(BaseModel):
    fetched: int
    missing: int


class RecomputeResult(BaseModel):
    updated: int
    missing: int


@router.get("/status", response_model=CurrencyStatus)
def currency_status(session: Session = Depends(get_session)) -> CurrencyStatus:
    return CurrencyStatus(**status(session))


@router.get("/rates", response_model=list[FxRateRow])
def get_rates(
    session: Session = Depends(get_session),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    base_currency: str | None = Query(default=None, min_length=3, max_length=3),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[FxRateRow]:
    return [
        FxRateRow.model_validate(row)
        for row in list_rates(
            session,
            currency=currency,
            base_currency=base_currency,
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
            base_currency=payload.base_currency or status(session)["base_currency"],
            rate_date=payload.rate_date,
            rate=payload.rate,
            source="manual",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    session.refresh(row)
    return FxRateRow.model_validate(row)


@router.post("/fetch-nbp", response_model=FetchNbpResult)
def fetch_nbp(session: Session = Depends(get_session)) -> FetchNbpResult:
    return FetchNbpResult(**fetch_nbp_rates_for_missing_transactions(session))


@router.post("/recompute", response_model=RecomputeResult)
def recompute(session: Session = Depends(get_session)) -> RecomputeResult:
    return RecomputeResult(**recompute_transactions(session))
