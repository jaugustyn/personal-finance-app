"""Shared anomaly review service used by API and LLM tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.currencies import BASE_CURRENCY, amount_base_expr, amount_base_value
from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.anomaly.detector import detect_anomalies
from finance.ml.feedback import (
    EVENT_ANOMALY_NOT_RELEVANT,
    EVENT_ANOMALY_RELEVANT,
    EVENT_ANOMALY_REVIEW_RESTORED,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.transactions.merchants import (
    MerchantIdentityResolver,
    load_merchant_identity_resolver,
)
from finance.transactions.type_decision import effective_transaction_type_expr

AnomalyMode = Literal["review", "suspicious", "all"]
AnomalyDirection = Literal["debit", "credit", "both"]
AnomalyReviewState = Literal["pending", "reviewed"]
AnomalyFeedbackStatus = Literal["relevant", "not_relevant"]
AnomalyFeedbackAction = Literal["relevant", "not_relevant", "restore"]


@dataclass(frozen=True)
class AnomalyFeedbackDecision:
    status: AnomalyFeedbackStatus
    reviewed_at: datetime


@dataclass(frozen=True)
class AnomalyReviewRow:
    id: int
    booking_date: date
    amount: Decimal
    base_currency: str
    direction: str
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    title: str
    category: str | None
    severity: float | None
    priority_score: float | None
    anomaly_type: str | None
    reasons: list[str]
    reason_codes: list[str]
    merchant_occurrences: int
    merchant_median_amount: float
    is_recurring_merchant: bool
    review_status: AnomalyFeedbackStatus | None = None
    reviewed_at: datetime | None = None
    currently_detected: bool = True


@dataclass(frozen=True)
class AnomalyReviewResult:
    items: list[AnomalyReviewRow]
    total: int
    pending_total: int
    reviewed_total: int


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
    amount = amount_base_expr()
    stmt = (
        select(
            Transaction.id.label("id"),
            Transaction.booking_date.label("booking_date"),
            amount.label("amount"),
            Transaction.direction.label("direction"),
            Transaction.merchant.label("merchant"),
            Transaction.title.label("title"),
            Transaction.category.label("category"),
            Transaction.is_transfer.label("is_transfer"),
            effective_transaction_type_expr().label("transaction_type"),
        )
        .where(amount.is_not(None))
        .order_by(Transaction.booking_date.desc())
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    rows = session.execute(stmt).mappings().all()
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["amount"] = frame["amount"].astype(float)
    frame["base_currency"] = BASE_CURRENCY
    frame["merchant"] = frame["merchant"].fillna("")
    frame["title"] = frame["title"].fillna("")
    resolver = load_merchant_identity_resolver(session)
    frame["merchant_key"] = [
        resolver.resolve(merchant, title).canonical_key
        for merchant, title in zip(
            frame["merchant"],
            frame["title"],
            strict=False,
        )
    ]
    return frame


ANOMALY_FEEDBACK_EVENT_TO_STATUS: dict[str, AnomalyFeedbackStatus] = {
    EVENT_ANOMALY_RELEVANT: "relevant",
    EVENT_ANOMALY_NOT_RELEVANT: "not_relevant",
}


def anomaly_feedback_decisions(
    session: Session,
    transaction_ids: set[int] | None = None,
) -> dict[int, AnomalyFeedbackDecision]:
    event_types = [
        EVENT_ANOMALY_RELEVANT,
        EVENT_ANOMALY_NOT_RELEVANT,
        EVENT_ANOMALY_REVIEW_RESTORED,
    ]
    stmt = select(
        MlFeedbackEvent.transaction_id,
        MlFeedbackEvent.event_type,
        MlFeedbackEvent.created_at,
    ).where(
        MlFeedbackEvent.entity_type == "anomaly_transaction",
        MlFeedbackEvent.transaction_id.is_not(None),
        MlFeedbackEvent.event_type.in_(event_types),
    )
    if transaction_ids is not None:
        if not transaction_ids:
            return {}
        stmt = stmt.where(MlFeedbackEvent.transaction_id.in_(transaction_ids))
    rows = session.execute(
        stmt.order_by(MlFeedbackEvent.created_at.asc(), MlFeedbackEvent.id.asc())
    ).all()
    decisions: dict[int, AnomalyFeedbackDecision] = {}
    for transaction_id, event_type, created_at in rows:
        if transaction_id is None:
            continue
        transaction_id = int(transaction_id)
        if event_type == EVENT_ANOMALY_REVIEW_RESTORED:
            decisions.pop(transaction_id, None)
            continue
        status = ANOMALY_FEEDBACK_EVENT_TO_STATUS.get(str(event_type))
        if status and created_at is not None:
            decisions[transaction_id] = AnomalyFeedbackDecision(
                status=status,
                reviewed_at=created_at,
            )
    return decisions


def anomaly_feedback_statuses(
    session: Session,
    transaction_ids: set[int],
) -> dict[int, AnomalyFeedbackStatus]:
    return {
        transaction_id: decision.status
        for transaction_id, decision in anomaly_feedback_decisions(
            session,
            transaction_ids,
        ).items()
    }


def reviewed_anomaly_transaction_ids(session: Session) -> set[int]:
    return set(anomaly_feedback_decisions(session))


def _with_merchant_identity(
    flagged: pd.DataFrame,
    resolver: MerchantIdentityResolver,
) -> pd.DataFrame:
    if flagged.empty:
        return flagged
    identities = [
        resolver.resolve(
            str(row.get("merchant") or ""),
            str(row.get("title") or ""),
        )
        for _, row in flagged.iterrows()
    ]
    out = flagged.copy()
    out["merchant_key"] = [identity.canonical_key for identity in identities]
    out["merchant_display"] = [identity.display_label for identity in identities]
    return out


def _apply_feedback(
    session: Session,
    flagged: pd.DataFrame,
    *,
    mode: AnomalyMode,
) -> pd.DataFrame:
    if flagged.empty:
        return flagged
    if mode == "review":
        reviewed = reviewed_anomaly_transaction_ids(session)
        if reviewed:
            flagged = flagged[~flagged["id"].astype(int).isin(reviewed)]
    return flagged


def _apply_mode(flagged: pd.DataFrame, *, mode: AnomalyMode) -> pd.DataFrame:
    if mode == "review":
        return flagged[flagged["priority_score"] >= 0.45]
    if mode == "suspicious":
        return flagged[
            flagged["anomaly_type"].isin(["suspicious", "data_quality", "merchant_amount_outlier"])
            & (flagged["priority_score"] >= 0.65)
        ]
    return flagged


def _to_row(
    raw: pd.Series,
    decision: AnomalyFeedbackDecision | None,
    *,
    currently_detected: bool = True,
) -> AnomalyReviewRow:
    booking_date = raw["booking_date"]
    if hasattr(booking_date, "date"):
        booking_date = booking_date.date()
    merchant = str(_clean(raw.get("merchant")) or "")
    merchant_display = str(_clean(raw.get("merchant_display")) or merchant)
    merchant_key = str(_clean(raw.get("merchant_key")) or "")
    category = _clean(raw.get("category"))
    return AnomalyReviewRow(
        id=int(raw["id"]),
        booking_date=booking_date,
        amount=Decimal(str(raw["amount"])),
        base_currency=str(raw["base_currency"]),
        direction=str(raw["direction"]),
        merchant=merchant,
        merchant_display=merchant_display,
        merchant_canonical_key=merchant_key,
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
        review_status=decision.status if decision else None,
        reviewed_at=decision.reviewed_at if decision else None,
        currently_detected=currently_detected,
    )


def _detect_flagged(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = 0.05,
    direction: AnomalyDirection | None = "debit",
    mode: AnomalyMode = "review",
    include_model_only: bool = False,
) -> pd.DataFrame:
    df = _transaction_frame(session, date_from=date_from, date_to=date_to)
    if df.empty:
        return pd.DataFrame()
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
    flagged = _apply_mode(flagged, mode=mode)
    return flagged.sort_values(["priority_score", "severity"], ascending=False)


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
    flagged = _detect_flagged(
        session,
        date_from=date_from,
        date_to=date_to,
        contamination=contamination,
        direction=direction,
        mode=mode,
        include_model_only=include_model_only,
    )
    if flagged.empty:
        return []
    if mode == "review":
        flagged = _apply_feedback(session, flagged, mode=mode)
    flagged = flagged.head(limit)
    flagged = _with_merchant_identity(
        flagged,
        load_merchant_identity_resolver(session),
    )
    transaction_ids = {int(raw["id"]) for _, raw in flagged.iterrows()}
    decisions = anomaly_feedback_decisions(session, transaction_ids)
    return [_to_row(raw, decisions.get(int(raw["id"]))) for _, raw in flagged.iterrows()]


def _historical_review_row(
    tx: Transaction,
    decision: AnomalyFeedbackDecision,
    *,
    resolver: MerchantIdentityResolver,
) -> AnomalyReviewRow:
    identity = resolver.resolve(tx.merchant, tx.title)
    base_amount = amount_base_value(tx)
    amount = base_amount if base_amount is not None else tx.amount
    currency = BASE_CURRENCY if base_amount is not None else tx.currency
    return AnomalyReviewRow(
        id=tx.id,
        booking_date=tx.booking_date,
        amount=amount,
        base_currency=currency,
        direction=tx.direction,
        merchant=tx.merchant or "",
        merchant_display=identity.display_label,
        merchant_canonical_key=identity.canonical_key,
        title=tx.title or "",
        category=tx.category,
        severity=None,
        priority_score=None,
        anomaly_type=None,
        reasons=[],
        reason_codes=[],
        merchant_occurrences=0,
        merchant_median_amount=0.0,
        is_recurring_merchant=False,
        review_status=decision.status,
        reviewed_at=decision.reviewed_at,
        currently_detected=False,
    )


def get_anomaly_review_result(
    session: Session,
    *,
    review_state: AnomalyReviewState = "pending",
    date_from: date | None = None,
    date_to: date | None = None,
    contamination: float = 0.05,
    direction: AnomalyDirection | None = "debit",
    limit: int | None = None,
) -> AnomalyReviewResult:
    flagged = _detect_flagged(
        session,
        date_from=date_from,
        date_to=date_to,
        contamination=contamination,
        direction=direction,
        mode="review",
        include_model_only=False,
    )
    decisions = anomaly_feedback_decisions(session)
    reviewed_ids = set(decisions)

    pending = (
        flagged[~flagged["id"].astype(int).isin(reviewed_ids)] if not flagged.empty else flagged
    )
    pending_total = len(pending)

    reviewed_filters: list[Any] = [Transaction.id.in_(reviewed_ids)]
    if direction not in (None, "both"):
        reviewed_filters.append(Transaction.direction == direction)
    if date_from is not None:
        reviewed_filters.append(Transaction.booking_date >= date_from)
    if date_to is not None:
        reviewed_filters.append(Transaction.booking_date <= date_to)
    if not reviewed_ids:
        reviewed_transactions: list[Transaction] = []
        reviewed_total = 0
    elif review_state == "pending":
        reviewed_transactions = []
        reviewed_total = int(
            session.scalar(select(func.count(Transaction.id)).where(*reviewed_filters)) or 0
        )
    else:
        reviewed_transactions = list(
            session.execute(select(Transaction).where(*reviewed_filters)).scalars()
        )
        reviewed_total = len(reviewed_transactions)

    if review_state == "pending":
        selected = pending if limit is None else pending.head(limit)
        if selected.empty:
            items: list[AnomalyReviewRow] = []
        else:
            selected = _with_merchant_identity(
                selected,
                load_merchant_identity_resolver(session),
            )
            items = [_to_row(raw, None) for _, raw in selected.iterrows()]
    else:
        resolver = load_merchant_identity_resolver(session)
        current_flagged = (
            flagged[flagged["id"].astype(int).isin(tx.id for tx in reviewed_transactions)]
            if not flagged.empty
            else flagged
        )
        current_flagged = _with_merchant_identity(current_flagged, resolver)
        current_rows = {
            int(raw["id"]): _to_row(raw, decisions.get(int(raw["id"])))
            for _, raw in current_flagged.iterrows()
        }
        reviewed_rows = [
            current_rows.get(tx.id)
            or _historical_review_row(
                tx,
                decisions[tx.id],
                resolver=resolver,
            )
            for tx in reviewed_transactions
            if tx.id in decisions
        ]
        reviewed_rows.sort(
            key=lambda row: row.reviewed_at.timestamp() if row.reviewed_at else 0.0,
            reverse=True,
        )
        items = reviewed_rows if limit is None else reviewed_rows[:limit]
    return AnomalyReviewResult(
        items=items,
        total=pending_total if review_state == "pending" else reviewed_total,
        pending_total=pending_total,
        reviewed_total=reviewed_total,
    )


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
        "restore": EVENT_ANOMALY_REVIEW_RESTORED,
    }[action]
    entity_key = str(transaction_id)
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=event_type,
            transaction_id=transaction_id,
            entity_type="anomaly_transaction",
            entity_key=entity_key,
            source="anomaly_detector",
        ),
    )
    session.commit()
    session.refresh(event)
    return event
