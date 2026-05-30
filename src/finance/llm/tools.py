"""Function-calling tool registry for the LLM assistant."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from finance.llm.insight_tools import forecast_for, list_anomalies, list_subscriptions
from finance.llm.recommendation_tools import recommend_savings
from finance.llm.review_tools import category_review_summary
from finance.llm.spending_tools import compare_periods, get_spending, top_merchants
from finance.llm.tool_schemas import (
    CategoryReviewArgs,
    ComparePeriodsArgs,
    ForecastArgs,
    GetSpendingArgs,
    ListAnomaliesArgs,
    ListSubscriptionsArgs,
    SavingsRecommendationsArgs,
    TopMerchantsArgs,
)

TOOLS: dict[str, Any] = {
    "get_spending": get_spending,
    "top_merchants": top_merchants,
    "list_subscriptions": list_subscriptions,
    "list_anomalies": list_anomalies,
    "forecast_for": forecast_for,
    "compare_periods": compare_periods,
    "recommend_savings": recommend_savings,
    "category_review_summary": category_review_summary,
}


def _schema(name: str, model: type[BaseModel], description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": model.model_json_schema(),
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _schema(
        "get_spending",
        GetSpendingArgs,
        "Suma wydatków w okresie, opcjonalnie filtr kategorii.",
    ),
    _schema("top_merchants", TopMerchantsArgs, "Top sprzedawców wg wydatków w okresie."),
    _schema(
        "list_subscriptions",
        ListSubscriptionsArgs,
        "Wykryte subskrypcje (cykliczne płatności).",
    ),
    _schema(
        "list_anomalies",
        ListAnomaliesArgs,
        "Nietypowe transakcje w okresie (Isolation Forest + reguły).",
    ),
    _schema("forecast_for", ForecastArgs, "Prognoza miesięcznych wydatków per kategoria."),
    _schema("compare_periods", ComparePeriodsArgs, "Porównaj sumy wydatków dla dwóch okresów."),
    _schema(
        "recommend_savings",
        SavingsRecommendationsArgs,
        "Wylicz rekomendacje oszczędnościowe z danych transakcji.",
    ),
    _schema(
        "category_review_summary",
        CategoryReviewArgs,
        "Podsumowanie kolejki ręcznego review sugestii kategorii.",
    ),
]

__all__ = [
    "ComparePeriodsArgs",
    "ForecastArgs",
    "GetSpendingArgs",
    "CategoryReviewArgs",
    "ListAnomaliesArgs",
    "ListSubscriptionsArgs",
    "SavingsRecommendationsArgs",
    "TOOLS",
    "TOOL_SCHEMAS",
    "TopMerchantsArgs",
    "compare_periods",
    "category_review_summary",
    "forecast_for",
    "get_spending",
    "list_anomalies",
    "list_subscriptions",
    "recommend_savings",
    "top_merchants",
]
