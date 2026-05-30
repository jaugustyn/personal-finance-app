"""Deterministic Polish intent router for finance questions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from finance.llm.periods import extract_all_periods, extract_period

CATEGORIES_PL = {
    "jedzenie": "food",
    "food": "food",
    "spożywcze": "food",
    "zakupy": "food",
    "transport": "transport",
    "paliwo": "transport",
    "uber": "transport",
    "subskrypcje": "subscriptions",
    "subskrypcja": "subscriptions",
    "rozrywka": "entertainment",
    "entertainment": "entertainment",
    "mieszkanie": "housing",
    "housing": "housing",
    "czynsz": "housing",
    "zdrowie": "health",
    "health": "health",
    "oszczędności": "savings",
    "oszczednosci": "savings",
    "savings": "savings",
}
_CATEGORY_PATTERNS = [
    (re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.I), category)
    for word, category in CATEGORIES_PL.items()
]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


def extract_category(question: str) -> str | None:
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(question):
            return category
    return None


def heuristic_route(question: str) -> ToolCall | None:
    """Map common Polish finance questions to one deterministic tool call."""
    q = question.lower().strip()
    period = extract_period(question)
    category = extract_category(question)

    if re.search(r"subskrypcj|cykliczn|abonamen", q):
        return ToolCall("list_subscriptions", {"min_confidence": 0.5})
    if re.search(r"anomali|nietypow|podejrzan|dziwn", q):
        return ToolCall("list_anomalies", {"period": period, "limit": 10})
    if re.search(r"prognoz|przewidu|przewidyw|forecast|przyszł", q):
        return ToolCall("forecast_for", {"category": category, "horizon": 3})
    if re.search(
        r"(do\s+przypisania|review|etykiet|kategoryzac|sugesti|confidence|pewno[sś]ci)",
        q,
    ):
        return ToolCall("category_review_summary", {"threshold": 0.55, "limit": 8})
    if re.search(
        r"oszcz[eę]dz|ogranicz|zreduk|rekomend|optymaliz|co mog[eę]|limit|bud[zż]et",
        q,
    ):
        return ToolCall("recommend_savings", {"period": period, "limit": 5})
    if re.search(r"top\s+(skle|sprzeda|merchant|firm)|gdzie\s+wyda|najwi[eę]ksz[ey].*wydat", q):
        return ToolCall("top_merchants", {"period": period, "limit": 5, "category": category})

    if re.search(r"por[óo]wn|r[óo]?[żz]nic", q):
        periods = extract_all_periods(question)
        if len(periods) >= 2:
            period_a, period_b = periods[0], periods[1]
        else:
            period_a = period or "this_month"
            period_b = "last_month"
        return ToolCall(
            "compare_periods",
            {"period_a": period_a, "period_b": period_b, "category": category},
        )

    if re.search(r"ile\s+(wyda[lł]|kosztu|zap[lł]aci)|suma\s+wydat|wydatk", q):
        return ToolCall("get_spending", {"period": period, "category": category})

    return None
