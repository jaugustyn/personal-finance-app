"""Small operational counters displayed in the application navigation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.assets.service import count_items_needing_review
from finance.domain.models import Transaction
from finance.ml.anomaly.service import get_anomaly_review_result
from finance.ml.subscriptions.service import list_subscription_rows
from finance.transactions.type_decision import fallback_type_expr


@dataclass(frozen=True)
class AttentionSummary:
    transaction_category_reviews: int
    transaction_type_reviews: int
    anomaly_reviews: int
    subscription_reviews: int
    asset_reviews: int

    @property
    def transaction_reviews(self) -> int:
        """Return the number of outstanding category and type decisions."""
        return self.transaction_category_reviews + self.transaction_type_reviews


def _transaction_review_counts(session: Session) -> tuple[int, int]:
    """Count actionable transaction decisions without loading review rows."""
    category_count = func.count(Transaction.id).filter(
        *expense_category_candidate_filters(),
        Transaction.category.is_(None),
        Transaction.category_suggestion_rejected.is_(False),
    )
    type_count = func.count(Transaction.id).filter(
        Transaction.transaction_type_confirmation_method.is_(None),
        Transaction.transaction_type_predicted.is_not(None),
        Transaction.transaction_type_predicted != fallback_type_expr(),
    )
    category_reviews, type_reviews = session.execute(
        select(category_count, type_count)
    ).one()
    return int(category_reviews or 0), int(type_reviews or 0)


def _pending_anomaly_count(session: Session) -> int:
    result = get_anomaly_review_result(
        session,
        review_state="pending",
        direction="both",
        limit=0,
    )
    return result.pending_total


def _pending_subscription_count(session: Session) -> int:
    rows = list_subscription_rows(
        session,
        min_confidence=0.0,
        include_rejected=False,
        include_details=False,
    )
    return sum(1 for row in rows if not row.is_confirmed)


def attention_summary(session: Session) -> AttentionSummary:
    """Build navigation counters without serializing any private row data."""
    category_reviews, type_reviews = _transaction_review_counts(session)
    return AttentionSummary(
        transaction_category_reviews=category_reviews,
        transaction_type_reviews=type_reviews,
        anomaly_reviews=_pending_anomaly_count(session),
        subscription_reviews=_pending_subscription_count(session),
        asset_reviews=count_items_needing_review(session),
    )
