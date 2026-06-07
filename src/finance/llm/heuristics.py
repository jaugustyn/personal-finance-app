"""Deterministic Polish intent router for finance questions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from finance.llm.periods import extract_all_periods, extract_period
from finance.transactions.normalization import normalize_text
from finance.transactions.system_rules import system_rules_registry

_POLISH_TRANSLATION = str.maketrans({"ł": "l", "Ł": "L"})


def normalize_question_text(question: str | None) -> str:
    """Normalise assistant questions, including Polish letters not handled by NFKD."""
    return normalize_text((question or "").translate(_POLISH_TRANSLATION))


_CATEGORY_ALIASES = system_rules_registry().llm_category_aliases
CATEGORIES_PL = dict(_CATEGORY_ALIASES)
_CATEGORY_PATTERNS = [
    (
        re.compile(rf"(?<!\w){re.escape(normalize_question_text(word))}(?!\w)", re.I),
        category,
    )
    for word, category in _CATEGORY_ALIASES
    if normalize_question_text(word)
]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


def extract_category(question: str) -> str | None:
    q = normalize_question_text(question)
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(q):
            return category
    return None


def heuristic_route(question: str) -> ToolCall | None:
    """Map common Polish finance questions to one deterministic tool call."""
    q = normalize_question_text(question)
    period = extract_period(question)
    category = extract_category(question)

    if re.search(r"subskrypcj|cykliczn|abonamen", q):
        return ToolCall("list_subscriptions", {"min_confidence": 0.5})
    if re.search(r"anomali|nietypow|podejrzan|dziwn", q):
        return ToolCall("list_anomalies", {"period": period, "limit": 10})
    if re.search(r"prognoz|przewidu|przewidyw|forecast|przyszl", q):
        return ToolCall("forecast_for", {"category": category, "horizon": 3})
    if re.search(
        r"(do\s+przypisania|review|etykiet|kategoryzac|sugesti|confidence|pewnosci)",
        q,
    ):
        return ToolCall("category_review_summary", {"threshold": 0.55, "limit": 8})
    if re.search(
        r"(cash\s?flow|przychod|zarob|wplyw|wplyn|dostalem|saldo|netto|"
        r"zaoszczedzil|oszczedzilem|przychody\s+vs\s+wydatki|"
        r"wydatki\s+vs\s+przychody)",
        q,
    ):
        return ToolCall("cashflow_overview", {"period": period})
    if re.search(
        r"(na\s+co.*(najwiecej|wydaj|wydal|wydatk|poszlo|idzie)|"
        r"co.*(pochlan|zjada|zabiera).*budzet|"
        r"najwieksz.*kategor|kategorie.*najwiecej|"
        r"struktura\s+wydat|podzial\s+wydat|rozklad\s+wydat)",
        q,
    ):
        return ToolCall("top_categories", {"period": period, "limit": 5})
    if re.search(
        r"oszczedz|ogranicz|zreduk|rekomend|optymaliz|co moge|limit|budzet",
        q,
    ):
        return ToolCall("recommend_savings", {"period": period, "limit": 5})
    if re.search(
        r"(top\s+(skle|sprzeda|merchant|firm)|gdzie.*(wyd|zaplac|posz)|"
        r"u\s+kogo|sprzedawc|sklep|odbiorc)",
        q,
    ):
        return ToolCall(
            "top_merchants",
            {"period": period, "limit": 5, "category": category},
        )

    if re.search(r"porown|roznic", q):
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

    if re.search(
        r"ile\s+(wydal|wydalem|wydaj|kosztu|zaplaci)|suma\s+wydat|wydatk",
        q,
    ):
        return ToolCall("get_spending", {"period": period, "category": category})

    return None
