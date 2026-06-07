"""Data-quality review aggregations (the "Review Center").

Surfaces the buckets that most improve ML training data: uncategorized
transactions, low-confidence suggestions, ready-to-accept suggestions, rejected
suggestions, rare categories and recurring merchants that have no personal rule
yet. Counts ignore own transfers and non-expense transaction types that should
not receive category suggestions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.domain.models import PersonalRule, Transaction
from finance.ml.feedback import (
    anomaly_feedback_summary,
    confusion_hotspots,
    feedback_quality,
    subscription_feedback_summary,
)
from finance.transactions.normalization import normalize_merchant

DEFAULT_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_RARE_CLASS_THRESHOLD = 40
DEFAULT_RECURRING_MIN_COUNT = 3
DEFAULT_RECURRING_LIMIT = 10


@dataclass(frozen=True)
class ReviewCounts:
    uncategorized: int
    no_suggestion: int
    low_confidence: int
    ready_to_accept: int
    rejected: int
    categorized: int


@dataclass(frozen=True)
class RareClass:
    category: str
    count: int


@dataclass(frozen=True)
class RecurringMerchant:
    merchant: str
    count: int


def _count(session: Session, *conditions: Any) -> int:
    stmt = select(func.count()).select_from(Transaction).where(
        *expense_category_candidate_filters(),
        *conditions,
    )
    return int(session.execute(stmt).scalar_one())


def review_counts(
    session: Session, *, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> ReviewCounts:
    uncategorized = _count(session, Transaction.category.is_(None))
    categorized = _count(session, Transaction.category.is_not(None))
    no_suggestion = _count(
        session,
        Transaction.category.is_(None),
        Transaction.category_predicted.is_(None),
        Transaction.category_suggestion_rejected.is_(False),
    )
    low_confidence = _count(
        session,
        Transaction.category.is_(None),
        Transaction.category_predicted.is_not(None),
        Transaction.category_suggestion_rejected.is_(False),
        Transaction.category_confidence.is_not(None),
        Transaction.category_confidence < threshold,
    )
    ready_to_accept = _count(
        session,
        Transaction.category.is_(None),
        Transaction.category_predicted.is_not(None),
        Transaction.category_suggestion_rejected.is_(False),
        Transaction.category_confidence.is_not(None),
        Transaction.category_confidence >= threshold,
    )
    rejected = _count(
        session,
        Transaction.category.is_(None),
        Transaction.category_suggestion_rejected.is_(True),
    )
    return ReviewCounts(
        uncategorized=uncategorized,
        no_suggestion=no_suggestion,
        low_confidence=low_confidence,
        ready_to_accept=ready_to_accept,
        rejected=rejected,
        categorized=categorized,
    )


def rare_classes(
    session: Session, *, threshold: int = DEFAULT_RARE_CLASS_THRESHOLD
) -> list[RareClass]:
    """Confirmed categories whose labelled count is below ``threshold``.

    These are the classes the classifier is most starved of; collecting more of
    them is the highest-leverage labelling action.
    """
    stmt = (
        select(Transaction.category, func.count().label("cnt"))
        .where(
            *expense_category_candidate_filters(),
            Transaction.category.is_not(None),
        )
        .group_by(Transaction.category)
        .having(func.count() < threshold)
        .order_by(func.count().asc())
    )
    rows = session.execute(stmt).all()
    return [RareClass(category=str(row.category), count=int(row.cnt)) for row in rows]


def recurring_unruled_merchants(
    session: Session,
    *,
    min_count: int = DEFAULT_RECURRING_MIN_COUNT,
    limit: int = DEFAULT_RECURRING_LIMIT,
) -> list[RecurringMerchant]:
    """Frequent uncategorized merchants that have no personal rule yet."""
    cnt = func.count().label("cnt")
    stmt = (
        select(Transaction.merchant, cnt)
        .where(
            *expense_category_candidate_filters(),
            Transaction.category.is_(None),
            Transaction.merchant != "",
        )
        .group_by(Transaction.merchant)
        .having(cnt >= min_count)
        .order_by(cnt.desc())
    )
    rows = session.execute(stmt).all()

    rule_norms = [
        norm
        for (norm,) in session.execute(
            select(PersonalRule.pattern_norm).where(PersonalRule.active.is_(True))
        ).all()
        if norm
    ]

    out: list[RecurringMerchant] = []
    for row in rows:
        merchant_norm = normalize_merchant(row.merchant)
        if any(rule in merchant_norm or merchant_norm in rule for rule in rule_norms):
            continue
        out.append(RecurringMerchant(merchant=row.merchant, count=int(row.cnt)))
        if len(out) >= limit:
            break
    return out


def review_summary(
    session: Session,
    *,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    rare_class_threshold: int = DEFAULT_RARE_CLASS_THRESHOLD,
    recurring_min_count: int = DEFAULT_RECURRING_MIN_COUNT,
    recurring_limit: int = DEFAULT_RECURRING_LIMIT,
) -> dict[str, Any]:
    counts = review_counts(session, threshold=threshold)
    return {
        "counts": counts,
        "rare_classes": rare_classes(session, threshold=rare_class_threshold),
        "recurring_unruled": recurring_unruled_merchants(
            session, min_count=recurring_min_count, limit=recurring_limit
        ),
        "feedback_quality": feedback_quality(session),
        "confusion_hotspots": confusion_hotspots(session),
        "anomaly_feedback": anomaly_feedback_summary(session),
        "subscription_feedback": subscription_feedback_summary(session),
        "confidence_threshold": threshold,
        "rare_class_threshold": rare_class_threshold,
    }
