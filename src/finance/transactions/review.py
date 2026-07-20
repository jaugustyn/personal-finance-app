"""Data-quality review aggregations (the "Review Center").

Surfaces the buckets that most improve ML training data: uncategorized
transactions, low-confidence suggestions, ready-to-accept suggestions, rejected
suggestions, rare categories and recurring merchants that have no personal rule
yet. Counts ignore own transfers and non-expense transaction types that should
not receive category suggestions.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.domain.enums import (
    CATEGORY_CONFIRMATION_METHOD_VALUES,
    TRANSACTION_TYPE_VALUES,
    Category,
)
from finance.domain.models import MlFeedbackEvent, PersonalRule, Transaction
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationPolicy,
    decide_classification,
)
from finance.ml.feedback import (
    anomaly_feedback_summary,
    confusion_hotspots,
    feedback_quality,
    subscription_feedback_summary,
)
from finance.transactions.merchants import load_merchant_alias_maps, merchant_identity
from finance.transactions.type_decision import (
    TYPE_GOLD_METHODS,
    effective_transaction_type,
    fallback_type_expr,
)
from finance.transactions.types import RareClass, RecurringMerchant, ReviewCounts

DEFAULT_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_RARE_CLASS_THRESHOLD = 40
DEFAULT_RECURRING_MIN_COUNT = 3
DEFAULT_RECURRING_LIMIT = 10


def _count(session: Session, *conditions: Any) -> int:
    stmt = select(func.count()).select_from(Transaction).where(
        *expense_category_candidate_filters(),
        *conditions,
    )
    return int(session.execute(stmt).scalar_one())


def review_counts(
    session: Session,
    *,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    policy: ClassificationPolicy = DEFAULT_POLICY,
) -> ReviewCounts:
    uncategorized = _count(session, Transaction.category.is_(None))
    categorized = _count(
        session,
        Transaction.category.in_([category.value for category in Category]),
        Transaction.category_confirmation_method.in_(
            CATEGORY_CONFIRMATION_METHOD_VALUES
        ),
        Transaction.category_confirmed_at.is_not(None),
    )
    no_suggestion = _count(
        session,
        Transaction.category.is_(None),
        Transaction.category_predicted.is_(None),
        Transaction.category_suggestion_rejected.is_(False),
    )
    suggested_rows = session.execute(
        select(Transaction).where(
            *expense_category_candidate_filters(),
            Transaction.category.is_(None),
            Transaction.category_predicted.is_not(None),
            Transaction.category_suggestion_rejected.is_(False),
        )
    ).scalars().all()
    ready_to_accept = 0
    low_confidence = 0
    for row in suggested_rows:
        decision = decide_classification(
            category=row.category_predicted,
            confidence=row.category_confidence,
            direction=row.direction,
            is_transfer=row.is_transfer,
            transaction_type=effective_transaction_type(row),
            policy=policy,
        )
        if decision.action == "accept":
            ready_to_accept += 1
        else:
            low_confidence += 1
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
            Transaction.category.in_([category.value for category in Category]),
            Transaction.category_confirmation_method.in_(
                CATEGORY_CONFIRMATION_METHOD_VALUES
            ),
            Transaction.category_confirmed_at.is_not(None),
        )
        .group_by(Transaction.category)
    )
    rows = session.execute(stmt).all()
    observed = {str(row.category): int(row.cnt) for row in rows}
    rare = [
        RareClass(category=category.value, count=observed.get(category.value, 0))
        for category in Category
        if observed.get(category.value, 0) < threshold
    ]
    return sorted(rare, key=lambda item: (item.count, item.category))


def recurring_unruled_merchants(
    session: Session,
    *,
    min_count: int = DEFAULT_RECURRING_MIN_COUNT,
    limit: int = DEFAULT_RECURRING_LIMIT,
) -> list[RecurringMerchant]:
    """Frequent uncategorized merchants that have no personal rule yet."""
    stmt = (
        select(Transaction.merchant, Transaction.title)
        .where(
            *expense_category_candidate_filters(),
            Transaction.category.is_(None),
            Transaction.merchant != "",
        )
    )
    rows = session.execute(stmt).all()

    rule_norms = [
        norm
        for (norm,) in session.execute(
            select(PersonalRule.pattern_norm).where(PersonalRule.active.is_(True))
        ).all()
        if norm
    ]

    alias_map, label_map = load_merchant_alias_maps(session)
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for row in rows:
        identity = merchant_identity(
            row.merchant,
            row.title,
            alias_map=alias_map,
            label_map=label_map,
        )
        merchant_key = identity.canonical_key
        if not merchant_key:
            continue
        labels.setdefault(merchant_key, identity.display_label or str(row.merchant))
        counts[merchant_key] = counts.get(merchant_key, 0) + 1

    out: list[RecurringMerchant] = []
    for merchant_key, count in sorted(
        counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        if count < min_count:
            continue
        merchant_norm = merchant_key
        if any(rule in merchant_norm or merchant_norm in rule for rule in rule_norms):
            continue
        out.append(
            RecurringMerchant(
                merchant=labels[merchant_key],
                merchant_display=labels[merchant_key],
                merchant_canonical_key=merchant_key,
                count=count,
            )
        )
        if len(out) >= limit:
            break
    return out


def review_summary(
    session: Session,
    *,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    policy: ClassificationPolicy = DEFAULT_POLICY,
    rare_class_threshold: int = DEFAULT_RARE_CLASS_THRESHOLD,
    recurring_min_count: int = DEFAULT_RECURRING_MIN_COUNT,
    recurring_limit: int = DEFAULT_RECURRING_LIMIT,
) -> dict[str, Any]:
    counts = review_counts(session, threshold=threshold, policy=policy)
    total_types = int(
        session.execute(select(func.count()).select_from(Transaction)).scalar_one()
    )
    confirmed_types = int(
        session.execute(
            select(func.count()).where(
                Transaction.transaction_type_confirmation_method.in_(TYPE_GOLD_METHODS)
            )
        ).scalar_one()
    )
    suggested_types = int(
        session.execute(
            select(func.count()).where(
                Transaction.transaction_type_predicted.is_not(None),
                Transaction.transaction_type_predicted != fallback_type_expr(),
            )
        ).scalar_one()
    )
    actionable_types = int(
        session.execute(
            select(func.count()).where(
                Transaction.transaction_type_confirmation_method.is_(None),
                Transaction.transaction_type_predicted.is_not(None),
                Transaction.transaction_type_predicted != fallback_type_expr(),
            )
        ).scalar_one()
    )
    type_class_counts = {
        str(value): int(count)
        for value, count in session.execute(
            select(Transaction.transaction_type, func.count())
            .where(Transaction.transaction_type_confirmation_method.in_(TYPE_GOLD_METHODS))
            .group_by(Transaction.transaction_type)
        ).all()
    }
    type_source_counts = {
        str(source or "unknown"): int(count)
        for source, count in session.execute(
            select(Transaction.transaction_type_source, func.count())
            .where(Transaction.transaction_type.is_not(None))
            .group_by(Transaction.transaction_type_source)
        ).all()
    }
    type_suggestion_source_counts = {
        str(source or "unknown"): int(count)
        for source, count in session.execute(
            select(Transaction.transaction_type_predicted_source, func.count())
            .where(
                Transaction.transaction_type_predicted.is_not(None),
                Transaction.transaction_type_predicted != fallback_type_expr(),
            )
            .group_by(Transaction.transaction_type_predicted_source)
        ).all()
    }
    type_corrections = [
        {
            "source": str(source or "unknown"),
            "suggested_or_previous": str(predicted or previous),
            "final": str(final),
            "count": int(count),
        }
        for source, predicted, previous, final, count in session.execute(
            select(
                MlFeedbackEvent.source,
                MlFeedbackEvent.predicted_transaction_type,
                MlFeedbackEvent.previous_transaction_type,
                MlFeedbackEvent.final_transaction_type,
                func.count(),
            )
            .select_from(MlFeedbackEvent)
            .join(Transaction, Transaction.id == MlFeedbackEvent.transaction_id)
            .where(MlFeedbackEvent.entity_type == "transaction_type")
            .where(MlFeedbackEvent.final_transaction_type.is_not(None))
            .where(
                func.coalesce(
                    MlFeedbackEvent.predicted_transaction_type,
                    MlFeedbackEvent.previous_transaction_type,
                )
                != MlFeedbackEvent.final_transaction_type
            )
            .group_by(
                MlFeedbackEvent.source,
                MlFeedbackEvent.predicted_transaction_type,
                MlFeedbackEvent.previous_transaction_type,
                MlFeedbackEvent.final_transaction_type,
            )
            .order_by(func.count().desc())
        ).all()
    ]
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
        "transaction_type_quality": {
            "total": total_types,
            "confirmed": confirmed_types,
            "provisional": max(total_types - confirmed_types, 0),
            "needs_review": actionable_types,
            "suggested": suggested_types,
            "confirmed_share": confirmed_types / total_types if total_types else None,
            "class_counts": type_class_counts,
            "source_counts": type_source_counts,
            "suggestion_source_counts": type_suggestion_source_counts,
            "corrections": type_corrections,
            "unsupported_classes": sorted(
                value
                for value in TRANSACTION_TYPE_VALUES
                if type_class_counts.get(value, 0) < 10
            ),
        },
        "confidence_threshold": policy.default_threshold,
        "rare_class_threshold": rare_class_threshold,
    }
