"""Shared transaction service contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

CategoryState = Literal[
    "all",
    "categorized",
    "uncategorized",
    "suggested",
    "assignable",
    "needs_review",
    "rejected",
]

TransactionTypeState = Literal[
    "all",
    "confirmed",
    "provisional",
    "needs_review",
    "suggested",
]

TransactionSortBy = Literal["date", "merchant", "amount"]
TransactionSortDirection = Literal["asc", "desc"]
MerchantGroupSortBy = Literal["merchant", "amount", "count"]


@dataclass(frozen=True)
class TransactionFilters:
    date_from: date | None = None
    date_to: date | None = None
    include_transfers: bool = True
    import_id: int | None = None
    merchant: str | None = None
    merchant_canonical_key: str | None = None
    search: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    direction: str | None = None
    category: str | None = None
    category_state: CategoryState = "all"
    has_suggestion: bool | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    transaction_type: str | None = None
    transaction_type_state: TransactionTypeState = "all"
    transaction_type_source: str | None = None
    review_priority: bool = False


@dataclass(frozen=True)
class CategorySummary:
    category: str | None
    total_debit: Decimal
    total_credit: Decimal
    count: int


@dataclass(frozen=True)
class MerchantGroupSummary:
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    count: int
    total_debit: Decimal
    total_credit: Decimal
    common_category: str | None
    sample_merchants: list[str]
    sample_titles: list[str]


@dataclass(frozen=True)
class FilterSummaryResult:
    count: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    unconverted_count: int


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
    merchant_display: str
    merchant_canonical_key: str
    count: int


@dataclass(frozen=True)
class MerchantIdentity:
    alias_key: str
    canonical_key: str
    display_label: str


@dataclass(frozen=True)
class MerchantCandidateVariant:
    alias_key: str
    alias_label: str
    count: int
    total_debit: Decimal


@dataclass(frozen=True)
class MerchantAliasSuggestion:
    alias_key: str
    alias_label: str
    canonical_key: str
    canonical_label: str
    count: int
    total_amount: Decimal


@dataclass(frozen=True)
class MerchantCandidate:
    canonical_key: str
    canonical_label: str
    suggested_label: str
    aliases: list[str]
    variants: list[MerchantCandidateVariant]
    count: int
    total_debit: Decimal
