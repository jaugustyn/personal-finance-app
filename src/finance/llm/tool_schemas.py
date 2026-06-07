"""Pydantic argument schemas for assistant function-calling tools."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GetSpendingArgs(BaseModel):
    period: str | None = Field(
        default=None,
        description="Okres np. 'ten miesiąc', 'kwiecień 2026', '2026-04'.",
    )
    category: str | None = Field(
        default=None,
        description="Filtr po kategorii (np. food, transport).",
    )


class TopMerchantsArgs(BaseModel):
    period: str | None = None
    limit: int = Field(default=5, ge=1, le=20)
    category: str | None = None


class TopCategoriesArgs(BaseModel):
    period: str | None = Field(
        default=None,
        description="Okres np. 'ten miesiąc', 'kwiecień 2026', '2026-04'.",
    )
    limit: int = Field(default=5, ge=1, le=20)


class CashflowOverviewArgs(BaseModel):
    period: str | None = Field(
        default=None,
        description="Okres np. 'ten miesiąc', 'kwiecień 2026', '2026-04'.",
    )


class ListSubscriptionsArgs(BaseModel):
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ListAnomaliesArgs(BaseModel):
    period: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ForecastArgs(BaseModel):
    category: str | None = None
    horizon: int = Field(default=3, ge=1, le=12)


class ComparePeriodsArgs(BaseModel):
    period_a: str
    period_b: str
    category: str | None = None


class SavingsRecommendationsArgs(BaseModel):
    period: str | None = Field(
        default=None,
        description="Okres rekomendacji np. 'ten miesiąc', 'kwiecień 2026', '2026-04'.",
    )
    limit: int = Field(default=5, ge=1, le=10)


class CategoryReviewArgs(BaseModel):
    threshold: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Próg niskiego confidence dla sugestii kategorii.",
    )
    accept_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Próg sugestii możliwych do szybkiego zaakceptowania.",
    )
    limit: int = Field(default=8, ge=1, le=20)
