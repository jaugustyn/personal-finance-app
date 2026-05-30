"""GET /anomalies — flagged transactions with severity score."""
from datetime import date
from decimal import Decimal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.domain.models import Transaction
from finance.ml.anomaly import detect_anomalies

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyRow(BaseModel):
    id: int
    booking_date: date
    amount: Decimal
    direction: str
    merchant: str
    title: str
    category: str | None
    severity: float
    reasons: list[str]


def _split_reasons(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


@router.get("", response_model=list[AnomalyRow])
def list_anomalies(
    session: Session = Depends(get_session),
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = Query(default=0.05, ge=0.005, le=0.3),
    direction: str | None = Query(default="debit", pattern="^(debit|credit|both)$"),
    limit: int = Query(default=50, le=500),
) -> list[AnomalyRow]:
    stmt = select(Transaction).order_by(Transaction.booking_date.desc())
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    rows = session.execute(stmt).scalars().all()
    if not rows:
        return []
    df = pd.DataFrame(
        [
            {
                "id": r.id,
                "booking_date": r.booking_date,
                "amount": float(r.amount),
                "direction": r.direction,
                "merchant": r.merchant or "",
                "title": r.title or "",
                "category": r.category,
                "is_transfer": r.is_transfer,
            }
            for r in rows
        ]
    )
    dir_filter = None if direction == "both" else direction
    res = detect_anomalies(df, contamination=contamination, direction=dir_filter)
    flagged = res.df[res.df["anomaly"]].sort_values("severity", ascending=False).head(limit)

    def _clean(v):
        # NaN / NaT → None for Pydantic.
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return v

    return [
        AnomalyRow(
            id=int(r["id"]),
            booking_date=r["booking_date"].date()
            if hasattr(r["booking_date"], "date") else r["booking_date"],
            amount=Decimal(str(r["amount"])),
            direction=r["direction"],
            merchant=_clean(r["merchant"]) or "",
            title=_clean(r["title"]) or "",
            category=_clean(r["category"]),
            severity=float(r["severity"]),
            reasons=_split_reasons(r["reasons"]),
        )
        for _, r in flagged.iterrows()
    ]
