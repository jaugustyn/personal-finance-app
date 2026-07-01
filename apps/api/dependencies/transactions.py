"""Shared transaction API dependencies."""
from __future__ import annotations

from datetime import date

from fastapi import Query

from finance.domain.enums import TransactionDirection, TransactionType
from finance.transactions import service as tx_service
from finance.transactions.types import CategoryState


def enum_value(value: object | None) -> str | None:
    if value is None:
        return None
    enum_value_ = getattr(value, "value", value)
    return str(enum_value_)


class TransactionFilterParams:
    """Reusable query parameters for endpoints that accept transaction filters."""

    def __init__(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        include_transfers: bool = Query(default=True),
        import_id: int | None = None,
        merchant: str | None = None,
        search: str | None = None,
        direction: TransactionDirection | None = None,
        category: str | None = None,
        category_state: CategoryState = Query(default="all"),
        has_suggestion: bool | None = Query(default=None),
        min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
        max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
        transaction_type: TransactionType | None = None,
        review_priority: bool = Query(default=False),
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        self.include_transfers = include_transfers
        self.import_id = import_id
        self.merchant = merchant
        self.search = search
        self.direction = direction
        self.category = category
        self.category_state = category_state
        self.has_suggestion = has_suggestion
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        self.transaction_type = transaction_type
        self.review_priority = review_priority

    def to_filters(self) -> tx_service.TransactionFilters:
        return tx_service.TransactionFilters(
            date_from=self.date_from,
            date_to=self.date_to,
            include_transfers=self.include_transfers,
            import_id=self.import_id,
            merchant=self.merchant,
            search=self.search,
            direction=enum_value(self.direction),
            category=self.category,
            category_state=self.category_state,
            has_suggestion=self.has_suggestion,
            min_confidence=self.min_confidence,
            max_confidence=self.max_confidence,
            transaction_type=enum_value(self.transaction_type),
            review_priority=self.review_priority,
        )
