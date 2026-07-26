"""Pydantic schemas for transaction API endpoints."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field

from finance.domain.enums import TransactionDirection, TransactionType

TransactionId = Annotated[int, Field(gt=0)]
TransactionTag = Annotated[str, Field(max_length=64)]


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
    account_id: int
    account_name: str
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
    merchant_raw: str | None = None
    merchant_display: str | None = None
    merchant_canonical_key: str | None = None
    merchant_alias_key: str | None = None
    title: str
    category: str | None
    subcategory: str | None = None
    category_source: str | None = None
    category_confirmation_method: str | None = None
    category_confirmed_at: datetime | None = None
    category_origin_ref: str | None = None
    category_predicted: str | None
    category_confidence: float | None
    category_predicted_source: str | None = None
    category_predicted_ref: str | None = None
    category_suggestion_rejected: bool = False
    raw_transaction_type: str | None = None
    transaction_type: str | None = None
    transaction_type_source: str | None = None
    transaction_type_confirmation_method: str | None = None
    transaction_type_confirmed_at: datetime | None = None
    transaction_type_origin_ref: str | None = None
    transaction_type_predicted: str | None = None
    transaction_type_confidence: float | None = None
    transaction_type_predicted_source: str | None = None
    transaction_type_predicted_ref: str | None = None
    transaction_type_effective: str | None = None
    transaction_type_is_provisional: bool = True
    transaction_type_needs_review: bool = False
    source: str
    is_transfer: bool = False
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    import_id: int | None = None
    classification_decision: ClassificationDecisionResponse | None = None

    model_config = {"from_attributes": True}


class ManualTransactionWrite(BaseModel):
    account_id: int = Field(gt=0)
    booking_date: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    direction: TransactionDirection
    merchant: str = Field(default="", max_length=256)
    title: str = Field(default="", max_length=512)
    transaction_type: TransactionType | None = None
    category: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1024)


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
    unconverted_count: int


class MerchantGroup(BaseModel):
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    count: int
    total_debit: Decimal
    total_credit: Decimal
    common_category: str | None
    sample_merchants: list[str]
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
    merchant_display: str
    merchant_canonical_key: str
    count: int


class ReviewSummary(BaseModel):
    counts: ReviewCounts
    rare_classes: list[RareClass]
    recurring_unruled: list[RecurringMerchant]
    feedback_quality: dict[str, Any] = Field(default_factory=dict)
    confusion_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    anomaly_feedback: dict[str, Any] = Field(default_factory=dict)
    subscription_feedback: dict[str, Any] = Field(default_factory=dict)
    transaction_type_quality: dict[str, Any] = Field(default_factory=dict)
    confidence_threshold: float
    rare_class_threshold: int


class CategoryUpdate(BaseModel):
    category: str | None = Field(max_length=64)
    subcategory: str | None = Field(default=None, max_length=64)
    remember_rule: bool = False


class TypeUpdate(BaseModel):
    transaction_type: TransactionType
    allow_direction_mismatch: bool = False


class AnnotationUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=1024)
    tags: list[TransactionTag] | None = Field(default=None, max_length=20)


class BulkCategorize(BaseModel):
    ids: list[TransactionId] | None = Field(default=None, max_length=1000)
    merchant: str | None = Field(default=None, max_length=256)
    merchant_canonical_key: str | None = Field(default=None, max_length=256)
    category: str | None = Field(default=None, max_length=64)
    mark_transfer: bool | None = None
    transaction_type: TransactionType | None = None
    allow_direction_mismatch: bool = False


class BulkResult(BaseModel):
    affected: int


class AcceptSuggestions(BaseModel):
    ids: list[TransactionId] | None = Field(default=None, max_length=1000)
    min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    manual: bool = False


class RejectSuggestions(BaseModel):
    ids: list[TransactionId] | None = Field(default=None, max_length=1000)


class BulkDelete(BaseModel):
    ids: list[TransactionId] = Field(default_factory=list, max_length=1000)
