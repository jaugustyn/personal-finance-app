"""Feedback loop helpers for ML/AI review actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.domain.models import MlFeedbackEvent, Transaction
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)

EVENT_ACCEPT_SUGGESTION = "accept_suggestion"
EVENT_REJECT_SUGGESTION = "reject_suggestion"
EVENT_MANUAL_CATEGORY = "manual_category"
EVENT_MANUAL_CLEAR = "manual_clear"
EVENT_AUTO_RULE_CATEGORY = "auto_rule_category"
EVENT_MANUAL_TRANSACTION_TYPE = "manual_transaction_type"
EVENT_ACCEPT_TRANSACTION_TYPE = "accept_transaction_type_suggestion"
EVENT_AUTO_TRANSACTION_TYPE = "auto_transaction_type"
EVENT_ANOMALY_RELEVANT = "anomaly_relevant"
EVENT_ANOMALY_NOT_RELEVANT = "anomaly_not_relevant"
EVENT_ANOMALY_IGNORE_MERCHANT = "anomaly_ignore_merchant"
EVENT_SUBSCRIPTION_CONFIRMED = "subscription_confirmed"
EVENT_SUBSCRIPTION_REJECTED = "subscription_rejected"
EVENT_SUBSCRIPTION_RESTORED = "subscription_restored"


@dataclass(frozen=True)
class FeedbackEventInput:
    event_type: str
    transaction_id: int | None = None
    entity_type: str | None = None
    entity_key: str | None = None
    predicted_category: str | None = None
    previous_category: str | None = None
    final_category: str | None = None
    predicted_transaction_type: str | None = None
    previous_transaction_type: str | None = None
    final_transaction_type: str | None = None
    confirmation_method: str | None = None
    origin_ref: str | None = None
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
        previous_category=event.previous_category,
        final_category=event.final_category,
        predicted_transaction_type=event.predicted_transaction_type,
        previous_transaction_type=event.previous_transaction_type,
        final_transaction_type=event.final_transaction_type,
        confirmation_method=event.confirmation_method,
        origin_ref=event.origin_ref,
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
    previous_category: str | None = None,
    confirmation_method: str | None = None,
    origin_ref: str | None = None,
    source: str | None = None,
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
            previous_category=previous_category,
            confirmation_method=confirmation_method,
            origin_ref=origin_ref,
            confidence=tx.category_confidence,
            source=source if source is not None else tx.category_predicted_source,
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


def feedback_report(
    session: Session,
    *,
    model_updated_at: datetime | None = None,
    labels_used_in_current_model: int | None = None,
    current_label_count: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Detailed feedback diagnostics for retraining and review planning."""
    quality = feedback_quality(session)
    since_model_filter = (
        (MlFeedbackEvent.created_at > model_updated_at)
        if model_updated_at is not None
        else None
    )
    since_model = 0
    if since_model_filter is not None:
        since_model = int(
            session.execute(
                select(func.count()).where(since_model_filter)
            ).scalar_one()
            or 0
        )

    alias_map, label_map = load_merchant_alias_maps(session)
    corrected_rows = session.execute(
        select(Transaction.merchant, Transaction.title)
        .select_from(MlFeedbackEvent)
        .join(Transaction, Transaction.id == MlFeedbackEvent.transaction_id)
        .where(
            MlFeedbackEvent.event_type.in_(
                [EVENT_REJECT_SUGGESTION, EVENT_MANUAL_CATEGORY, EVENT_MANUAL_CLEAR]
            )
        )
    ).all()
    corrected_counts: dict[str, dict[str, Any]] = {}
    for merchant, title in corrected_rows:
        identity = merchant_identity(
            merchant,
            title,
            alias_map=alias_map,
            label_map=label_map,
        )
        if not identity.canonical_key:
            continue
        row = corrected_counts.setdefault(
            identity.canonical_key,
            {
                "merchant": identity.display_label or merchant_display_label(merchant, title),
                "count": 0,
            },
        )
        row["count"] += 1

    corrections = session.execute(
        select(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.final_category,
            MlFeedbackEvent.event_type,
            func.count().label("cnt"),
        )
        .where(MlFeedbackEvent.predicted_category.is_not(None))
        .where(
            (MlFeedbackEvent.event_type == EVENT_REJECT_SUGGESTION)
            | (
                MlFeedbackEvent.final_category.is_not(None)
                & (MlFeedbackEvent.final_category != MlFeedbackEvent.predicted_category)
            )
        )
        .group_by(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.final_category,
            MlFeedbackEvent.event_type,
        )
        .order_by(func.count().desc())
        .limit(limit)
    ).all()

    category_feedback = session.execute(
        select(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.event_type,
            func.count().label("cnt"),
        )
        .where(MlFeedbackEvent.predicted_category.is_not(None))
        .where(
            MlFeedbackEvent.event_type.in_(
                [EVENT_ACCEPT_SUGGESTION, EVENT_REJECT_SUGGESTION]
            )
        )
        .group_by(MlFeedbackEvent.predicted_category, MlFeedbackEvent.event_type)
    ).all()
    by_category: dict[str, dict[str, int]] = {}
    for category, event_type, count in category_feedback:
        bucket = by_category.setdefault(str(category), {"accepted": 0, "rejected": 0})
        if event_type == EVENT_ACCEPT_SUGGESTION:
            bucket["accepted"] = int(count)
        elif event_type == EVENT_REJECT_SUGGESTION:
            bucket["rejected"] = int(count)

    new_labels = None
    label_growth_ratio = None
    if labels_used_in_current_model is not None and current_label_count is not None:
        new_labels = max(current_label_count - labels_used_in_current_model, 0)
        if labels_used_in_current_model > 0:
            label_growth_ratio = new_labels / labels_used_in_current_model

    return {
        "quality": quality,
        "feedback_events_since_model": since_model,
        "feedback_events_used_in_training": None,
        "feedback_events_not_yet_in_model": since_model if model_updated_at else None,
        "feedback_coverage": None,
        "coverage_basis": "not_tracked_per_event",
        "labels_used_in_current_model": labels_used_in_current_model,
        "current_label_count": current_label_count,
        "new_labels_since_training": new_labels,
        "new_labels_since_training_ratio": label_growth_ratio,
        "top_corrected_merchants": sorted(
            corrected_counts.values(),
            key=lambda item: item["count"],
            reverse=True,
        )[:limit],
        "category_corrections": [
            {
                "predicted_category": predicted,
                "final_category": final,
                "event_type": event_type,
                "count": int(count),
            }
            for predicted, final, event_type, count in corrections
        ],
        "rejection_by_category": [
            {
                "category": category,
                "accepted": values["accepted"],
                "rejected": values["rejected"],
                "rejection_rate": (
                    values["rejected"] / (values["accepted"] + values["rejected"])
                    if values["accepted"] + values["rejected"]
                    else None
                ),
            }
            for category, values in sorted(
                by_category.items(),
                key=lambda item: item[1]["rejected"],
                reverse=True,
            )
        ],
    }


def confusion_hotspots(session: Session, *, limit: int = 10) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            MlFeedbackEvent.predicted_category,
            MlFeedbackEvent.final_category,
            MlFeedbackEvent.event_type,
            Transaction.merchant,
            Transaction.title,
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
            Transaction.title,
        )
        .order_by(func.count().desc())
    ).all()
    alias_map, label_map = load_merchant_alias_maps(session)
    grouped: dict[tuple[Any, Any, Any, str], dict[str, Any]] = {}
    for predicted, final, event_type, merchant, title, count in rows:
        identity = merchant_identity(
            merchant,
            title,
            alias_map=alias_map,
            label_map=label_map,
        )
        key = (predicted, final, event_type, identity.canonical_key)
        item = grouped.setdefault(
            key,
            {
                "predicted_category": predicted,
                "final_category": final,
                "event_type": event_type,
                "merchant": identity.display_label
                or merchant_display_label(merchant, title),
                "count": 0,
            },
        )
        item["count"] += int(count)
    return sorted(grouped.values(), key=lambda item: item["count"], reverse=True)[:limit]


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
    rejected = session.execute(
        select(func.count()).where(
            MlFeedbackEvent.event_type == EVENT_SUBSCRIPTION_REJECTED
        )
    ).scalar_one()
    restored = session.execute(
        select(func.count()).where(
            MlFeedbackEvent.event_type == EVENT_SUBSCRIPTION_RESTORED
        )
    ).scalar_one()
    return {
        "confirmed": int(confirmed or 0),
        "rejected": int(rejected or 0),
        "restored": int(restored or 0),
        "reviewed": int(confirmed or 0) + int(rejected or 0),
    }
