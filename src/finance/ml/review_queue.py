"""Prioritized review queue for category-quality work."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.domain.category_mapping import map_source_category
from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    OTHER_CATEGORY,
    ClassificationPolicy,
    decide_classification,
)
from finance.profile.service import effect_for_transaction
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_canonical_key,
    merchant_identity,
)

RARE_LABEL_THRESHOLD = 20
WEAK_LABEL_THRESHOLD = 50


@dataclass(frozen=True)
class ReviewQueueItem:
    transaction_id: int
    booking_date: date
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    title: str
    amount: Decimal
    currency: str
    direction: str
    predicted_category: str | None
    confidence: float | None
    decision_action: str
    decision_reason: str
    priority_score: float
    priority_components: dict[str, float]
    reason_codes: list[str]


def _category_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Transaction.category, func.count().label("cnt"))
        .where(*expense_category_candidate_filters())
        .where(Transaction.category.is_not(None))
        .group_by(Transaction.category)
    ).all()
    return {str(category): int(count) for category, count in rows}


def _merchant_candidate_counts(session: Session, alias_map: dict[str, str]) -> dict[str, int]:
    rows = session.execute(
        select(Transaction.merchant, Transaction.title)
        .where(*expense_category_candidate_filters())
        .where(Transaction.category.is_(None))
    ).all()
    counts: dict[str, int] = {}
    for merchant, title in rows:
        key = merchant_canonical_key(merchant, title, alias_map=alias_map)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _merchant_feedback_counts(session: Session, alias_map: dict[str, str]) -> dict[str, int]:
    rows = session.execute(
        select(Transaction.merchant, Transaction.title)
        .select_from(MlFeedbackEvent)
        .join(Transaction, Transaction.id == MlFeedbackEvent.transaction_id)
        .where(
            MlFeedbackEvent.event_type.in_(
                ["manual_category", "reject_suggestion", "manual_clear"]
            )
        )
    ).all()
    counts: dict[str, int] = {}
    for merchant, title in rows:
        key = merchant_canonical_key(merchant, title, alias_map=alias_map)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _uncertainty_score(action: str, confidence: float | None) -> tuple[float, str]:
    if action == "manual":
        return 35.0, "manual_required"
    if action == "review":
        if confidence is None:
            return 28.0, "review_without_confidence"
        return round(20.0 + ((1.0 - confidence) * 15.0), 2), "review_confidence"
    if action == "accept":
        return 5.0, "safe_suggestion"
    return 0.0, "not_applicable"


def _rare_category_score(
    category: str | None,
    category_counts: dict[str, int],
) -> tuple[float, str | None]:
    if not category:
        return 8.0, "missing_prediction"
    count = category_counts.get(category, 0)
    if count < RARE_LABEL_THRESHOLD:
        return 18.0, "rare_predicted_category"
    if count < WEAK_LABEL_THRESHOLD:
        return 9.0, "weak_predicted_category"
    return 0.0, None


def _conflict_score(session: Session, tx: Transaction) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    source_category = map_source_category(tx.raw_category)
    predicted = str(tx.category_predicted) if tx.category_predicted else None
    if source_category is not None and predicted and source_category.value != predicted:
        score += 12.0
        reasons.append("bank_model_conflict")

    personal = effect_for_transaction(session, merchant=tx.merchant, title=tx.title)
    if personal and personal.category and predicted and personal.category != predicted:
        score += 15.0
        reasons.append("rule_model_conflict")
    return min(score, 20.0), reasons


def review_queue(
    session: Session,
    *,
    limit: int = 50,
    policy: ClassificationPolicy = DEFAULT_POLICY,
) -> list[ReviewQueueItem]:
    """Return the highest-value category review items first."""
    rows = session.execute(
        select(Transaction)
        .where(*expense_category_candidate_filters())
        .where(Transaction.category.is_(None))
    ).scalars().all()
    if not rows:
        return []

    alias_map, label_map = load_merchant_alias_maps(session)
    category_counts = _category_counts(session)
    merchant_counts = _merchant_candidate_counts(session, alias_map)
    merchant_feedback = _merchant_feedback_counts(session, alias_map)
    max_amount_log = (
        max(
            math.log1p(
                abs(float((row.amount_base if row.amount_base is not None else row.amount) or 0))
            )
            for row in rows
        )
        or 1.0
    )

    items: list[ReviewQueueItem] = []
    for tx in rows:
        decision = decide_classification(
            category=tx.category_predicted,
            confidence=tx.category_confidence,
            direction=tx.direction,
            is_transfer=tx.is_transfer,
            transaction_type=tx.transaction_type,
            policy=policy,
        )
        uncertainty, uncertainty_reason = _uncertainty_score(
            decision.action,
            tx.category_confidence,
        )
        base_amount = tx.amount_base if tx.amount_base is not None else tx.amount
        amount_score = round(
            (math.log1p(abs(float(base_amount or 0))) / max_amount_log) * 20.0,
            2,
        )
        rare_score, rare_reason = _rare_category_score(
            tx.category_predicted,
            category_counts,
        )
        merchant_identity_ = merchant_identity(
            tx.merchant,
            tx.title,
            alias_map=alias_map,
            label_map=label_map,
        )
        merchant_key = merchant_identity_.canonical_key
        cluster_count = merchant_counts.get(merchant_key, 0)
        cluster_score = float(min(max(cluster_count - 1, 0) * 3, 15))
        feedback_score = float(min(merchant_feedback.get(merchant_key, 0) * 5, 15))
        conflict_score, conflict_reasons = _conflict_score(session, tx)
        other_score = 0.0
        other_reason = None
        if tx.category_predicted == OTHER_CATEGORY:
            other_score = 20.0 if decision.confidence else 10.0
            other_reason = "other_prediction"

        components = {
            "uncertainty": uncertainty,
            "amount_impact": amount_score,
            "rare_category": rare_score,
            "merchant_cluster": cluster_score,
            "feedback_history": feedback_score,
            "rule_model_conflict": conflict_score,
            "other_risk": other_score,
        }
        reason_codes = [
            uncertainty_reason,
            *(["large_amount"] if amount_score >= 15 else []),
            *(["merchant_cluster"] if cluster_score > 0 else []),
            *(["merchant_feedback_history"] if feedback_score > 0 else []),
            *(conflict_reasons),
            *([rare_reason] if rare_reason else []),
            *([other_reason] if other_reason else []),
        ]
        score = round(sum(components.values()), 2)
        items.append(
            ReviewQueueItem(
                transaction_id=int(tx.id),
                booking_date=tx.booking_date,
                merchant=str(tx.merchant or ""),
                merchant_display=merchant_identity_.display_label,
                merchant_canonical_key=merchant_key,
                title=str(tx.title or ""),
                amount=base_amount,
                currency=str(tx.base_currency or tx.currency),
                direction=str(tx.direction),
                predicted_category=tx.category_predicted,
                confidence=tx.category_confidence,
                decision_action=decision.action,
                decision_reason=decision.reason_code,
                priority_score=score,
                priority_components=components,
                reason_codes=list(dict.fromkeys(reason_codes)),
            )
        )

    items.sort(
        key=lambda item: (
            -item.priority_score,
            -abs(float(item.amount or 0)),
            item.booking_date,
            item.transaction_id,
        )
    )
    return items[:limit]
