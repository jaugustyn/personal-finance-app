"""Pydantic schemas for ML API endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from finance.domain.enums import BankSource, TransactionDirection, TransactionType
from finance.ml.classification.status import CONFIDENCE_RECOMMENDATION_THRESHOLD


class ClassifyRequest(BaseModel):
    merchant: str = ""
    title: str = ""
    amount: Decimal
    booking_date: date
    source: str = BankSource.UNKNOWN.value
    transaction_type: TransactionType = TransactionType.PURCHASE
    direction: TransactionDirection | None = None
    is_transfer: bool = False
    use_llm_fallback: bool = False
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)


class ClassificationDecisionResponse(BaseModel):
    action: str
    reason_code: str
    threshold_used: float
    review_floor: float
    category: str | None = None
    confidence: float | None = None
    category_candidate: bool


class ClassifyResponse(BaseModel):
    category: str
    confidence: float | None = None
    source: str = "model"
    model_category: str | None = None
    threshold: float = 0.55
    threshold_used: float = 0.55
    fallback_used: bool = False
    top_predictions: list[dict[str, Any]] = Field(default_factory=list)
    recommended_action: str = "review"
    classification_decision: ClassificationDecisionResponse


class ReclassifyResponse(BaseModel):
    updated: int


class RetrainResponse(BaseModel):
    status: str
    message: str


class RetrainStatusResponse(BaseModel):
    status: str = "idle"
    message: str | None = None
    estimator: str | None = None
    feature_set: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class MlFeedbackRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=48)
    transaction_id: int | None = None
    entity_type: str | None = Field(default=None, max_length=48)
    entity_key: str | None = Field(default=None, max_length=255)
    predicted_category: str | None = None
    final_category: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = None
    model_artifact: str | None = None


class MlFeedbackResponse(BaseModel):
    id: int | None = None
    status: str = "recorded"


class MlMetricSummary(BaseModel):
    model: str | None = None
    macro_f1: float | None = None
    weighted_f1: float | None = None
    coverage_at_055: float | None = None
    accuracy_at_055: float | None = None


class MlModelComparison(BaseModel):
    estimator: str
    feature_set: str
    rank: int | None = None
    macro_f1: float | None = None
    weighted_f1: float | None = None
    coverage_at_055: float | None = None
    accuracy_at_055: float | None = None
    time_holdout_macro_f1: float | None = None
    merchant_group_macro_f1: float | None = None
    stability_score: float | None = None
    confidence_note: str | None = None
    skipped: bool = False
    error: str | None = None
    is_recommended: bool = False
    is_current: bool = False


class MlModelRecommendation(BaseModel):
    estimator: str
    feature_set: str
    reason_code: str
    action_codes: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    macro_f1: float | None = None
    weighted_f1: float | None = None
    coverage_at_055: float | None = None
    accuracy_at_055: float | None = None
    confidence_threshold: float = CONFIDENCE_RECOMMENDATION_THRESHOLD
    based_on_report: bool = False
    feature_decision_reason: str | None = None


class MlModelStatus(BaseModel):
    exists: bool
    path: str
    updated_at: str | None = None
    estimator: str | None = None
    feature_set: str | None = None
    classes: list[str] = Field(default_factory=list)
    known_categories: list[str] = Field(default_factory=list)
    missing_categories: list[str] = Field(default_factory=list)
    extra_classes: list[str] = Field(default_factory=list)
    n_total_labelled: int | None = None
    n_classes: int | None = None
    report_path: str | None = None
    report_updated_at: str | None = None
    best_model: MlMetricSummary | None = None
    load_error: str | None = None
    artifact_metadata: dict[str, Any] = Field(default_factory=dict)
    compatibility_warnings: list[str] = Field(default_factory=list)
    retrain_signal: dict[str, Any] | None = None


class MlReadinessResponse(BaseModel):
    level: str
    total_labelled: int
    minimum_total: int
    recommended_total: int
    ideal_total: int
    minimum_per_category: int
    recommended_per_category: int
    strong_per_category: int
    category_counts: dict[str, int]
    below_minimum_per_category: list[str]
    below_recommended_per_category: list[str]
    date_span_months: int | None = None
    recommended_history_months: str
    training_labels_source: str
    category_predicted_is_ground_truth: bool
    next_review_priority: list[str]


class MlLatestReportResponse(BaseModel):
    path: str | None = None
    updated_at: str | None = None
    report: dict[str, Any] | None = None


class MlComparisonResponse(BaseModel):
    models: list[MlModelComparison] = Field(default_factory=list)
    recommendation: MlModelRecommendation


class MlDashboardResponse(BaseModel):
    status: MlModelStatus
    readiness: MlReadinessResponse
    latest_report: MlLatestReportResponse
    model_comparison: list[MlModelComparison] = Field(default_factory=list)
    recommendation: MlModelRecommendation
    validation_slices: dict[str, Any] = Field(default_factory=dict)
    confidence_policy: dict[str, Any] = Field(default_factory=dict)
    feedback_quality: dict[str, Any] = Field(default_factory=dict)
    feedback_report: dict[str, Any] = Field(default_factory=dict)
    retrain_signal: dict[str, Any] = Field(default_factory=dict)
    confusion_hotspots: list[dict[str, Any]] = Field(default_factory=list)


class ReviewQueueItemResponse(BaseModel):
    transaction_id: int
    booking_date: date
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    title: str
    amount: Decimal
    currency: str
    direction: str
    predicted_category: str | None = None
    confidence: float | None = None
    decision_action: str
    decision_reason: str
    priority_score: float
    priority_components: dict[str, float]
    reason_codes: list[str]


class FeedbackReportResponse(BaseModel):
    quality: dict[str, Any]
    feedback_events_since_model: int
    feedback_events_used_in_training: int | None = None
    feedback_events_not_yet_in_model: int | None = None
    feedback_coverage: float | None = None
    coverage_basis: str
    labels_used_in_current_model: int | None = None
    current_label_count: int | None = None
    new_labels_since_training: int | None = None
    new_labels_since_training_ratio: float | None = None
    top_corrected_merchants: list[dict[str, Any]] = Field(default_factory=list)
    category_corrections: list[dict[str, Any]] = Field(default_factory=list)
    rejection_by_category: list[dict[str, Any]] = Field(default_factory=list)
