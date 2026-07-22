"""Function-calling tool registry for the LLM assistant."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from finance.llm.insight_tools import forecast_for, list_anomalies, list_subscriptions
from finance.llm.recommendation_tools import recommend_savings
from finance.llm.review_tools import category_review_summary
from finance.llm.spending_tools import (
    cashflow_overview,
    compare_periods,
    get_spending,
    top_categories,
    top_merchants,
)
from finance.llm.tool_schemas import (
    CashflowOverviewArgs,
    CategoryReviewArgs,
    ComparePeriodsArgs,
    ForecastArgs,
    GetSpendingArgs,
    ListAnomaliesArgs,
    ListSubscriptionsArgs,
    SavingsRecommendationsArgs,
    TopCategoriesArgs,
    TopMerchantsArgs,
)
from finance.llm.types import ToolResult

ToolFunction = Callable[[Session, dict[str, Any]], ToolResult]

TOOLS: dict[str, ToolFunction] = {
    "get_spending": get_spending,
    "top_merchants": top_merchants,
    "top_categories": top_categories,
    "cashflow_overview": cashflow_overview,
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
        "top_categories",
        TopCategoriesArgs,
        "Top potwierdzonych kategorii wydatków w okresie.",
    ),
    _schema(
        "cashflow_overview",
        CashflowOverviewArgs,
        "Przychody, wydatki netto, zwroty, dług, alokacje i przepływ netto w okresie.",
    ),
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
    "CashflowOverviewArgs",
    "CategoryReviewArgs",
    "ListAnomaliesArgs",
    "ListSubscriptionsArgs",
    "SavingsRecommendationsArgs",
    "TopCategoriesArgs",
    "TOOLS",
    "TOOL_SCHEMAS",
    "TopMerchantsArgs",
    "cashflow_overview",
    "compare_periods",
    "category_review_summary",
    "forecast_for",
    "get_spending",
    "list_anomalies",
    "list_subscriptions",
    "recommend_savings",
    "top_categories",
    "top_merchants",
]
