"""Pydantic schemas for transaction API endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from finance.domain.enums import TransactionType


class ClassificationDecisionResponse(BaseModel):
    action: str
    reason_code: str
    threshold_used: float
    review_floor: float
    category: str | None = None
    confidence: float | None = None
    category_candidate: bool


class TransactionRow(BaseModel):
    id: int
    booking_date: date
    amount: Decimal
    currency: str
    amount_base: Decimal | None = None
    base_currency: str | None = None
    fx_rate: Decimal | None = None
    fx_rate_date: date | None = None
    fx_rate_source: str | None = None
    direction: str
    merchant: str
    title: str
    category: str | None
    subcategory: str | None = None
    category_source: str | None = None
    category_predicted: str | None
    category_confidence: float | None
    category_predicted_source: str | None = None
    category_suggestion_rejected: bool = False
    transaction_type: str = TransactionType.PURCHASE.value
    source: str
    is_transfer: bool = False
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    import_id: int | None = None
    classification_decision: ClassificationDecisionResponse | None = None

    model_config = {"from_attributes": True}


class CategorySum(BaseModel):
    category: str | None
    total_debit: Decimal
    total_credit: Decimal
    count: int


class FilterSummaryResponse(BaseModel):
    count: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal


class MerchantGroup(BaseModel):
    merchant: str
    count: int
    total_debit: Decimal
    total_credit: Decimal
    common_category: str | None
    sample_titles: list[str]


class ReviewCounts(BaseModel):
    uncategorized: int
    no_suggestion: int
    low_confidence: int
    ready_to_accept: int
    rejected: int
    categorized: int


class RareClass(BaseModel):
    category: str
    count: int


class RecurringMerchant(BaseModel):
    merchant: str
    count: int


class ReviewSummary(BaseModel):
    counts: ReviewCounts
    rare_classes: list[RareClass]
    recurring_unruled: list[RecurringMerchant]
    feedback_quality: dict[str, Any] = Field(default_factory=dict)
    confusion_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    anomaly_feedback: dict[str, Any] = Field(default_factory=dict)
    subscription_feedback: dict[str, Any] = Field(default_factory=dict)
    confidence_threshold: float
    rare_class_threshold: int


class CategoryUpdate(BaseModel):
    category: str | None
    subcategory: str | None = None
    remember_rule: bool = False


class TypeUpdate(BaseModel):
    transaction_type: TransactionType


class AnnotationUpdate(BaseModel):
    notes: str | None = None
    tags: list[str] | None = None


class BulkCategorize(BaseModel):
    ids: list[int] | None = None
    merchant: str | None = None
    category: str | None = None
    mark_transfer: bool | None = None
    transaction_type: TransactionType | None = None


class BulkResult(BaseModel):
    affected: int


class AcceptSuggestions(BaseModel):
    ids: list[int] | None = None
    min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    manual: bool = False


class RejectSuggestions(BaseModel):
    ids: list[int] | None = None


class BulkDelete(BaseModel):
    ids: list[int] = Field(default_factory=list)
