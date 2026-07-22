"""Typed result contracts for deterministic LLM tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

ToolResult = dict[str, Any]


def tool_result(model: BaseModel) -> ToolResult:
    """Return a JSON-serializable dict after Pydantic contract validation."""
    return model.model_dump(mode="json")


class PeriodRange(BaseModel):
    start: str
    end: str


class GetSpendingResult(BaseModel):
    period: PeriodRange
    category: str | None
    total: float
    currency: str
    transactions: int


class MerchantSpend(BaseModel):
    merchant: str
    total: float
    transactions: int


class TopMerchantsResult(BaseModel):
    period: PeriodRange
    category: str | None
    currency: str
    merchants: list[MerchantSpend]


class CategorySpend(BaseModel):
    category: str
    total: float
    transactions: int
    share: float


class TopCategoriesResult(BaseModel):
    period: PeriodRange
    currency: str
    total_candidate_spend: float
    categorized_total: float
    uncategorized_total: float
    category_coverage: float
    transactions: int
    categories: list[CategorySpend]


class CashflowOverviewResult(BaseModel):
    period: PeriodRange
    currency: str
    income: float
    gross_expenses: float
    refunds: float
    expenses: float
    debt_payments: float
    asset_allocations: float
    net: float
    savings_rate: float
    transactions: int


class PeriodTotal(BaseModel):
    start: str
    end: str
    total: float


class ComparePeriodsResult(BaseModel):
    category: str | None
    currency: str
    a: PeriodTotal
    b: PeriodTotal
    delta: float
    delta_pct: float | None


class SubscriptionToolItem(BaseModel):
    merchant: str
    status: str
    cadence: str
    median_amount: float | None
    occurrences: int
    confidence: float | None
    estimated_monthly_cost: float | None


class ListSubscriptionsResult(BaseModel):
    base_currency: str
    subscriptions: list[SubscriptionToolItem]
    estimated_monthly_cost: float


class AnomalyToolItem(BaseModel):
    id: int
    booking_date: str
    merchant: str
    amount: float | None
    base_currency: str
    severity: float | None
    priority_score: float | None
    anomaly_type: str
    reasons: list[str]
    feedback_status: str | None


class ListAnomaliesResult(BaseModel):
    period: PeriodRange
    anomalies: list[AnomalyToolItem]


class ForecastPoint(BaseModel):
    month: str
    amount: float | None


class ForecastResult(BaseModel):
    category: str | None
    base_currency: str
    error: str | None = None
    history_months: int = 0
    active_months: int = 0
    required_history_months: int = 0
    required_active_months: int = 0
    model: str | None = None
    mape: float | None = None
    rmse: float | None = None
    forecast: list[ForecastPoint] = Field(default_factory=list)


class CategoryOpportunity(BaseModel):
    kind: str
    category: str
    current_total: float
    previous_total: float
    delta: float
    delta_pct: float | None


class SubscriptionSummary(BaseModel):
    count: int
    estimated_monthly_cost: float


class AnomalySummary(BaseModel):
    count: int
    max_severity: float


class SavingsRecommendationResult(BaseModel):
    period: PeriodRange
    previous_period: PeriodRange
    total_current: float
    total_previous: float
    delta: float
    base_currency: str
    income: float
    actual_savings: float
    category_opportunities: list[CategoryOpportunity]
    top_merchants: list[MerchantSpend]
    subscriptions: SubscriptionSummary
    anomalies: AnomalySummary


class PredictedCategorySummary(BaseModel):
    category: str
    count: int


class CategoryReviewSummaryResult(BaseModel):
    threshold: float
    accept_threshold: float
    total_uncategorized: int
    without_suggestion: int
    suggested: int
    low_confidence: int
    high_confidence: int
    rejected: int
    by_predicted_category: list[PredictedCategorySummary]
    next_action: str
