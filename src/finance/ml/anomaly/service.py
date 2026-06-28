"""Shared anomaly review service used by API and LLM tools."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.anomaly.detector import detect_anomalies
from finance.ml.feedback import (
    EVENT_ANOMALY_IGNORE_MERCHANT,
    EVENT_ANOMALY_NOT_RELEVANT,
    EVENT_ANOMALY_RELEVANT,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.transactions.merchants import merchant_canonical_key

AnomalyMode = Literal["review", "suspicious", "all"]
AnomalyDirection = Literal["debit", "credit", "both"]
AnomalyFeedbackStatus = Literal["relevant", "not_relevant", "ignore_merchant"]
AnomalyFeedbackAction = AnomalyFeedbackStatus


@dataclass(frozen=True)
class AnomalyReviewRow:
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
    feedback_status: AnomalyFeedbackStatus | None = None


def split_reasons(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _clean(value: object) -> object | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _transaction_frame(
    session: Session,
    *,
    date_from: date | None,
    date_to: date | None,
) -> pd.DataFrame:
    stmt = select(Transaction).order_by(Transaction.booking_date.desc())
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    rows = session.execute(stmt).scalars().all()
    return pd.DataFrame(
        [
            {
                "id": row.id,
                "booking_date": row.booking_date,
                "amount": float(row.amount_base if row.amount_base is not None else row.amount),
                "direction": row.direction,
                "merchant": row.merchant or "",
                "title": row.title or "",
                "category": row.category,
                "is_transfer": row.is_transfer,
                "transaction_type": row.transaction_type,
            }
            for row in rows
        ]
    )


def ignored_anomaly_merchants(session: Session) -> set[str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key).where(
            MlFeedbackEvent.event_type == EVENT_ANOMALY_IGNORE_MERCHANT,
            MlFeedbackEvent.entity_type == "anomaly_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        )
    ).scalars()
    return {str(row) for row in rows if row}


def anomaly_priority_adjustments(session: Session) -> dict[str, float]:
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
    return {key: max(-0.5, min(0.25, value)) for key, value in adjustments.items()}


ANOMALY_FEEDBACK_EVENT_TO_STATUS: dict[str, AnomalyFeedbackStatus] = {
    EVENT_ANOMALY_RELEVANT: "relevant",
    EVENT_ANOMALY_NOT_RELEVANT: "not_relevant",
    EVENT_ANOMALY_IGNORE_MERCHANT: "ignore_merchant",
}


def anomaly_feedback_statuses(
    session: Session,
    merchants: list[str],
) -> dict[str, AnomalyFeedbackStatus]:
    keys = {merchant_canonical_key(merchant) for merchant in merchants}
    keys.discard("")
    if not keys:
        return {}
    rows = session.execute(
        select(MlFeedbackEvent.entity_key, MlFeedbackEvent.event_type)
        .where(
            MlFeedbackEvent.entity_type == "anomaly_merchant",
            MlFeedbackEvent.entity_key.in_(keys),
            MlFeedbackEvent.event_type.in_(ANOMALY_FEEDBACK_EVENT_TO_STATUS),
        )
        .order_by(MlFeedbackEvent.created_at.asc(), MlFeedbackEvent.id.asc())
    ).all()
    statuses: dict[str, AnomalyFeedbackStatus] = {}
    for key, event_type in rows:
        status = ANOMALY_FEEDBACK_EVENT_TO_STATUS.get(str(event_type))
        if key and status:
            statuses[str(key)] = status
    return statuses


def _apply_feedback(
    session: Session,
    flagged: pd.DataFrame,
    *,
    mode: AnomalyMode,
) -> pd.DataFrame:
    if flagged.empty:
        return flagged
    if mode != "all":
        ignored = ignored_anomaly_merchants(session)
        if ignored:
            flagged = flagged[
                ~flagged["merchant"].fillna("").map(merchant_canonical_key).isin(ignored)
            ]
    adjustments = anomaly_priority_adjustments(session)
    if adjustments and not flagged.empty:
        flagged = flagged.copy()
        flagged["priority_score"] = flagged.apply(
            lambda row: max(
                0.0,
                min(
                    1.0,
                    float(row["priority_score"])
                    + adjustments.get(
                        merchant_canonical_key(str(row.get("merchant") or "")),
                        0.0,
                    ),
                ),
            ),
            axis=1,
        )
    return flagged


def _apply_mode(flagged: pd.DataFrame, *, mode: AnomalyMode) -> pd.DataFrame:
    if mode == "review":
        return flagged[flagged["priority_score"] >= 0.45]
    if mode == "suspicious":
        return flagged[
            flagged["anomaly_type"].isin(
                ["suspicious", "data_quality", "merchant_amount_outlier"]
            )
            & (flagged["priority_score"] >= 0.65)
        ]
    return flagged


def _to_row(raw: pd.Series, feedback_status: AnomalyFeedbackStatus | None) -> AnomalyReviewRow:
    booking_date = raw["booking_date"]
    if hasattr(booking_date, "date"):
        booking_date = booking_date.date()
    merchant = str(_clean(raw.get("merchant")) or "")
    category = _clean(raw.get("category"))
    return AnomalyReviewRow(
        id=int(raw["id"]),
        booking_date=booking_date,
        amount=Decimal(str(raw["amount"])),
        direction=str(raw["direction"]),
        merchant=merchant,
        title=str(_clean(raw.get("title")) or ""),
        category=str(category) if category is not None else None,
        severity=float(raw.get("severity") or 0.0),
        priority_score=float(raw.get("priority_score") or 0.0),
        anomaly_type=str(raw.get("anomaly_type") or "none"),
        reasons=split_reasons(raw.get("reasons")),
        reason_codes=split_reasons(raw.get("reason_codes")),
        merchant_occurrences=int(raw.get("merchant_occurrences") or 0),
        merchant_median_amount=float(raw.get("merchant_median_amount") or 0.0),
        is_recurring_merchant=bool(raw.get("is_recurring_merchant")),
        feedback_status=feedback_status,
    )


def list_anomaly_rows(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = 0.05,
    direction: AnomalyDirection | None = "debit",
    limit: int = 50,
    mode: AnomalyMode = "review",
    include_model_only: bool = False,
) -> list[AnomalyReviewRow]:
    df = _transaction_frame(session, date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    dir_filter = None if direction in (None, "both") else direction
    scored = detect_anomalies(df, contamination=contamination, direction=dir_filter).df
    flagged = scored[scored["anomaly"]].copy()
    if "priority_score" not in flagged.columns:
        flagged["priority_score"] = flagged.get("severity", 0.0)
    if "severity" not in flagged.columns:
        flagged["severity"] = 0.0
    if "anomaly_type" not in flagged.columns:
        flagged["anomaly_type"] = "none"
    if not include_model_only:
        flagged = flagged[flagged["anomaly_type"] != "model_only"]
    flagged = _apply_feedback(session, flagged, mode=mode)
    flagged = _apply_mode(flagged, mode=mode)
    flagged = flagged.sort_values(["priority_score", "severity"], ascending=False).head(limit)
    statuses = anomaly_feedback_statuses(
        session,
        [str(value or "") for value in flagged["merchant"].tolist()],
    )
    return [
        _to_row(raw, statuses.get(merchant_canonical_key(str(raw.get("merchant") or ""))))
        for _, raw in flagged.iterrows()
    ]


def record_anomaly_feedback(
    session: Session,
    *,
    transaction_id: int,
    action: AnomalyFeedbackAction,
) -> MlFeedbackEvent | None:
    tx = session.get(Transaction, transaction_id)
    if tx is None:
        return None
    event_type = {
        "relevant": EVENT_ANOMALY_RELEVANT,
        "not_relevant": EVENT_ANOMALY_NOT_RELEVANT,
        "ignore_merchant": EVENT_ANOMALY_IGNORE_MERCHANT,
    }[action]
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=event_type,
            transaction_id=transaction_id,
            entity_type="anomaly_merchant",
            entity_key=merchant_canonical_key(tx.merchant, tx.title),
            source="anomaly_detector",
        ),
    )
    session.commit()
    session.refresh(event)
    return event
