"""Feedback loop helpers for ML/AI review actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.domain.models import MlFeedbackEvent, Transaction

EVENT_ACCEPT_SUGGESTION = "accept_suggestion"
EVENT_REJECT_SUGGESTION = "reject_suggestion"
EVENT_MANUAL_CATEGORY = "manual_category"
EVENT_MANUAL_CLEAR = "manual_clear"
EVENT_ANOMALY_RELEVANT = "anomaly_relevant"
EVENT_ANOMALY_NOT_RELEVANT = "anomaly_not_relevant"
EVENT_ANOMALY_IGNORE_MERCHANT = "anomaly_ignore_merchant"
EVENT_SUBSCRIPTION_CONFIRMED = "subscription_confirmed"
EVENT_SUBSCRIPTION_HIDDEN = "subscription_hidden"


@dataclass(frozen=True)
class FeedbackEventInput:
    event_type: str
    transaction_id: int | None = None
    entity_type: str | None = None
    entity_key: str | None = None
    predicted_category: str | None = None
    final_category: str | None = None
    confidence: float | None = None
    source: str | None = None
    model_artifact: str | None = None


def record_feedback_event(
    session: Session,
    event: FeedbackEventInput,
) -> MlFeedbackEvent:
    row = MlFeedbackEvent(
        transaction_id=event.transaction_id,
        entity_type=event.entity_type,
        entity_key=event.entity_key,
        event_type=event.event_type,
        predicted_category=event.predicted_category,
        final_category=event.final_category,
        confidence=event.confidence,
        source=event.source,
        model_artifact=event.model_artifact,
    )
    session.add(row)
    return row


def record_transaction_feedback(
    session: Session,
    tx: Transaction,
    *,
    event_type: str,
    final_category: str | None = None,
    model_artifact: str | None = None,
) -> MlFeedbackEvent:
    return record_feedback_event(
        session,
        FeedbackEventInput(
            transaction_id=tx.id,
            entity_type="transaction",
            entity_key=str(tx.id) if tx.id is not None else None,
            event_type=event_type,
            predicted_category=str(tx.category_predicted)
            if tx.category_predicted is not None
            else None,
            final_category=final_category,
            confidence=tx.category_confidence,
            source=tx.category_predicted_source,
            model_artifact=model_artifact,
        ),
    )


def feedback_quality(session: Session) -> dict[str, Any]:
    rows = session.execute(
        select(MlFeedbackEvent.event_type, func.count().label("cnt"))
        .group_by(MlFeedbackEvent.event_type)
    ).all()
    by_type = {str(event_type): int(count) for event_type, count in rows}
    accepted = by_type.get(EVENT_ACCEPT_SUGGESTION, 0)
    rejected = by_type.get(EVENT_REJECT_SUGGESTION, 0)
    manual = by_type.get(EVENT_MANUAL_CATEGORY, 0)
    suggestion_total = accepted + rejected

    category_rows = session.execute(
        select(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.event_type,
            func.count().label("cnt"),
        )
        .where(MlFeedbackEvent.predicted_category.is_not(None))
        .group_by(MlFeedbackEvent.predicted_category, MlFeedbackEvent.event_type)
    ).all()
    by_category: dict[str, dict[str, int]] = {}
    for category, event_type, count in category_rows:
        key = str(category)
        by_category.setdefault(key, {})
        by_category[key][str(event_type)] = int(count)

    return {
        "total_events": int(sum(by_type.values())),
        "by_event_type": by_type,
        "accepted_suggestions": accepted,
        "rejected_suggestions": rejected,
        "manual_category_events": manual,
        "suggestion_feedback_total": suggestion_total,
        "acceptance_rate": accepted / suggestion_total if suggestion_total else None,
        "rejection_rate": rejected / suggestion_total if suggestion_total else None,
        "by_predicted_category": [
            {
                "category": category,
                "accepted": events.get(EVENT_ACCEPT_SUGGESTION, 0),
                "rejected": events.get(EVENT_REJECT_SUGGESTION, 0),
                "manual": events.get(EVENT_MANUAL_CATEGORY, 0),
            }
            for category, events in sorted(by_category.items())
        ],
    }


def confusion_hotspots(session: Session, *, limit: int = 10) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.final_category,
            MlFeedbackEvent.event_type,
            Transaction.merchant,
            func.count().label("cnt"),
        )
        .outerjoin(Transaction, Transaction.id == MlFeedbackEvent.transaction_id)
        .where(MlFeedbackEvent.predicted_category.is_not(None))
        .where(
            (MlFeedbackEvent.event_type == EVENT_REJECT_SUGGESTION)
            | (
                (MlFeedbackEvent.final_category.is_not(None))
                & (MlFeedbackEvent.final_category != MlFeedbackEvent.predicted_category)
            )
        )
        .group_by(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.final_category,
            MlFeedbackEvent.event_type,
            Transaction.merchant,
        )
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return [
        {
            "predicted_category": predicted,
            "final_category": final,
            "event_type": event_type,
            "merchant": merchant,
            "count": int(count),
        }
        for predicted, final, event_type, merchant, count in rows
    ]


def anomaly_feedback_summary(session: Session) -> dict[str, Any]:
    relevant = session.execute(
        select(func.count()).where(
            MlFeedbackEvent.event_type == EVENT_ANOMALY_RELEVANT
        )
    ).scalar_one()
    not_relevant = session.execute(
        select(func.count()).where(
            MlFeedbackEvent.event_type == EVENT_ANOMALY_NOT_RELEVANT
        )
    ).scalar_one()
    reviewed = int(relevant or 0) + int(not_relevant or 0)
    return {
        "reviewed": reviewed,
        "relevant": int(relevant or 0),
        "not_relevant": int(not_relevant or 0),
        "precision": int(relevant or 0) / reviewed if reviewed else None,
        "precision_at_20": int(relevant or 0) / reviewed if reviewed else None,
    }


def subscription_feedback_summary(session: Session) -> dict[str, Any]:
    confirmed = session.execute(
        select(func.count()).where(
            MlFeedbackEvent.event_type == EVENT_SUBSCRIPTION_CONFIRMED
        )
    ).scalar_one()
    hidden = session.execute(
        select(func.count()).where(
            MlFeedbackEvent.event_type == EVENT_SUBSCRIPTION_HIDDEN
        )
    ).scalar_one()
    return {
        "confirmed": int(confirmed or 0),
        "hidden": int(hidden or 0),
        "reviewed": int(confirmed or 0) + int(hidden or 0),
    }
