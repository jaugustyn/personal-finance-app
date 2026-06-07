"""GET /anomalies — flagged transactions with severity score."""
from datetime import date
from decimal import Decimal
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.anomaly import detect_anomalies
from finance.ml.feedback import (
    EVENT_ANOMALY_IGNORE_MERCHANT,
    EVENT_ANOMALY_NOT_RELEVANT,
    EVENT_ANOMALY_RELEVANT,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.transactions.normalization import normalize_merchant

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
    priority_score: float
    anomaly_type: str
    reasons: list[str]
    reason_codes: list[str]
    merchant_occurrences: int
    merchant_median_amount: float
    is_recurring_merchant: bool
    feedback_status: Literal["relevant", "not_relevant", "ignore_merchant"] | None = None


class AnomalyFeedbackRequest(BaseModel):
    action: Literal["relevant", "not_relevant", "ignore_merchant"]


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    id: int | None = None


def _split_reasons(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _split_codes(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _ignored_anomaly_merchants(session: Session) -> set[str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key).where(
            MlFeedbackEvent.event_type == EVENT_ANOMALY_IGNORE_MERCHANT,
            MlFeedbackEvent.entity_type == "anomaly_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        )
    ).scalars()
    return {str(row) for row in rows if row}


def _anomaly_priority_adjustments(session: Session) -> dict[str, float]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key, MlFeedbackEvent.event_type).where(
            MlFeedbackEvent.entity_type == "anomaly_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
            MlFeedbackEvent.event_type.in_(
                [EVENT_ANOMALY_RELEVANT, EVENT_ANOMALY_NOT_RELEVANT]
            ),
        )
    ).all()
    adjustments: dict[str, float] = {}
    for key, event_type in rows:
        delta = 0.08 if event_type == EVENT_ANOMALY_RELEVANT else -0.15
        adjustments[str(key)] = adjustments.get(str(key), 0.0) + delta
    return {
        key: max(-0.5, min(0.25, value))
        for key, value in adjustments.items()
    }


ANOMALY_FEEDBACK_EVENT_TO_STATUS = {
    EVENT_ANOMALY_RELEVANT: "relevant",
    EVENT_ANOMALY_NOT_RELEVANT: "not_relevant",
    EVENT_ANOMALY_IGNORE_MERCHANT: "ignore_merchant",
}


def _anomaly_feedback_statuses(
    session: Session,
    merchants: list[str],
) -> dict[str, Literal["relevant", "not_relevant", "ignore_merchant"]]:
    keys = {normalize_merchant(merchant) for merchant in merchants}
    keys.discard("")
    if not keys:
        return {}
    rows = session.execute(
        select(
            MlFeedbackEvent.entity_key,
            MlFeedbackEvent.event_type,
        )
        .where(
            MlFeedbackEvent.entity_type == "anomaly_merchant",
            MlFeedbackEvent.entity_key.in_(keys),
            MlFeedbackEvent.event_type.in_(ANOMALY_FEEDBACK_EVENT_TO_STATUS),
        )
        .order_by(MlFeedbackEvent.created_at.asc(), MlFeedbackEvent.id.asc())
    ).all()
    statuses: dict[str, Literal["relevant", "not_relevant", "ignore_merchant"]] = {}
    for key, event_type in rows:
        status = ANOMALY_FEEDBACK_EVENT_TO_STATUS.get(str(event_type))
        if key and status:
            statuses[str(key)] = status
    return statuses


@router.get("", response_model=list[AnomalyRow])
def list_anomalies(
    session: Session = Depends(get_session),
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = Query(default=0.05, ge=0.005, le=0.3),
    direction: str | None = Query(default="debit", pattern="^(debit|credit|both)$"),
    limit: int = Query(default=50, le=500),
    mode: Literal["review", "suspicious", "all"] = Query(default="review"),
    include_model_only: bool = Query(default=False),
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
                "transaction_type": r.transaction_type,
            }
            for r in rows
        ]
    )
    dir_filter = None if direction == "both" else direction
    res = detect_anomalies(df, contamination=contamination, direction=dir_filter)
    flagged = res.df[res.df["anomaly"]].copy()
    if not include_model_only:
        flagged = flagged[flagged["anomaly_type"] != "model_only"]
    if mode != "all":
        ignored = _ignored_anomaly_merchants(session)
        if ignored:
            flagged = flagged[
                ~flagged["merchant"].fillna("").map(normalize_merchant).isin(ignored)
            ]
    adjustments = _anomaly_priority_adjustments(session)
    if adjustments and not flagged.empty:
        flagged["priority_score"] = flagged.apply(
            lambda row: max(
                0.0,
                min(
                    1.0,
                    float(row["priority_score"])
                    + adjustments.get(normalize_merchant(row.get("merchant") or ""), 0.0),
                ),
            ),
            axis=1,
        )
    if mode == "review":
        flagged = flagged[flagged["priority_score"] >= 0.45]
    elif mode == "suspicious":
        flagged = flagged[
            flagged["anomaly_type"].isin(
                ["suspicious", "data_quality", "merchant_amount_outlier"]
            )
            & (flagged["priority_score"] >= 0.65)
        ]
    flagged = (
        flagged.sort_values(["priority_score", "severity"], ascending=False)
        .head(limit)
    )
    feedback_statuses = _anomaly_feedback_statuses(
        session,
        [str(value or "") for value in flagged["merchant"].tolist()],
    )

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
            priority_score=float(r["priority_score"]),
            anomaly_type=str(r["anomaly_type"]),
            reasons=_split_reasons(r["reasons"]),
            reason_codes=_split_codes(r.get("reason_codes")),
            merchant_occurrences=int(r.get("merchant_occurrences") or 0),
            merchant_median_amount=float(r.get("merchant_median_amount") or 0.0),
            is_recurring_merchant=bool(r.get("is_recurring_merchant")),
            feedback_status=feedback_statuses.get(
                normalize_merchant(_clean(r["merchant"]) or "")
            ),
        )
        for _, r in flagged.iterrows()
    ]


@router.post("/{transaction_id}/feedback", response_model=FeedbackResponse)
def record_anomaly_feedback(
    transaction_id: int,
    req: AnomalyFeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    tx = session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    event_type = {
        "relevant": EVENT_ANOMALY_RELEVANT,
        "not_relevant": EVENT_ANOMALY_NOT_RELEVANT,
        "ignore_merchant": EVENT_ANOMALY_IGNORE_MERCHANT,
    }[req.action]
    entity_type = "anomaly_merchant"
    entity_key = normalize_merchant(tx.merchant)
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=event_type,
            transaction_id=transaction_id,
            entity_type=entity_type,
            entity_key=entity_key,
            source="anomaly_detector",
        ),
    )
    session.commit()
    session.refresh(event)
    return FeedbackResponse(id=event.id)
