"""Deterministic tools for category review and active-learning diagnostics."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.domain.models import Transaction
from finance.llm.tool_schemas import CategoryReviewArgs
from finance.llm.types import (
    CategoryReviewSummaryResult,
    PredictedCategorySummary,
    ToolResult,
    tool_result,
)


def category_review_summary(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = CategoryReviewArgs(**args)

    base = (
        select(func.count())
        .where(Transaction.category.is_(None))
        .where(*expense_category_candidate_filters())
    )
    total_uncategorized = int(session.execute(base).scalar() or 0)
    without_suggestion = int(
        session.execute(base.where(Transaction.category_predicted.is_(None))).scalar() or 0
    )
    rejected = int(
        session.execute(
            base.where(Transaction.category_suggestion_rejected.is_(True))
        ).scalar()
        or 0
    )
    suggested = int(
        session.execute(
            base.where(Transaction.category_predicted.is_not(None)).where(
                Transaction.category_suggestion_rejected.is_(False)
            )
        ).scalar()
        or 0
    )
    low_confidence = int(
        session.execute(
            base.where(Transaction.category_predicted.is_not(None))
            .where(Transaction.category_suggestion_rejected.is_(False))
            .where(Transaction.category_confidence < parsed.threshold)
        ).scalar()
        or 0
    )
    high_confidence = int(
        session.execute(
            base.where(Transaction.category_predicted.is_not(None))
            .where(Transaction.category_suggestion_rejected.is_(False))
            .where(Transaction.category_confidence >= parsed.accept_threshold)
        ).scalar()
        or 0
    )

    category_rows = session.execute(
        select(Transaction.category_predicted, func.count().label("n"))
        .where(Transaction.category.is_(None))
        .where(*expense_category_candidate_filters())
        .where(Transaction.category_predicted.is_not(None))
        .where(Transaction.category_suggestion_rejected.is_(False))
        .group_by(Transaction.category_predicted)
        .order_by(func.count().desc())
        .limit(parsed.limit)
    ).all()

    if without_suggestion:
        next_action = "Najpierw ręcznie przypisz transakcje bez sugestii."
    elif low_confidence:
        next_action = "Następnie sprawdź sugestie o niskim confidence."
    elif high_confidence:
        next_action = "Możesz zaakceptować wysokie confidence zbiorczo po szybkim review."
    else:
        next_action = "Kolejka review jest pusta albo wymaga ponownego reclassify."

    return tool_result(
        CategoryReviewSummaryResult(
            threshold=parsed.threshold,
            accept_threshold=parsed.accept_threshold,
            total_uncategorized=total_uncategorized,
            without_suggestion=without_suggestion,
            suggested=suggested,
            low_confidence=low_confidence,
            high_confidence=high_confidence,
            rejected=rejected,
            by_predicted_category=[
                PredictedCategorySummary(category=str(category), count=int(count))
                for category, count in category_rows
            ],
            next_action=next_action,
        )
    )
