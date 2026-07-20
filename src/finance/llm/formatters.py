"""Deterministic Polish answer formatters for LLM tool results."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

from finance.llm.types import ToolResult

_CATEGORY_LABELS_PL = {
    "food": "Jedzenie",
    "transport": "Transport i podróże",
    "subscriptions": "Subskrypcje",
    "health": "Zdrowie",
    "entertainment": "Rozrywka",
    "housing": "Dom i rachunki",
    "savings": "Oszczędności",
    "shopping": "Zakupy",
    "other": "Inne",
}

Formatter = Callable[[ToolResult], str]


_CADENCE_LABELS_PL = {
    "weekly": "co tydzień",
    "biweekly": "co 2 tygodnie",
    "monthly": "co miesiąc",
    "yearly": "co rok",
    "unknown": "nieregularnie",
}

_FORECAST_MODEL_LABELS_PL = {
    "naive": "ostatni miesiąc",
    "mean3": "średnia z 3 miesięcy",
    "ses": "wygładzanie wykładnicze",
    "holt_damped": "trend tłumiony",
    "seasonal_naive": "wzorzec roczny",
}


def fmt_money(value: float | None, currency: str | None = None) -> str:
    """Format a monetary value without assuming PLN as the profile currency."""
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        numeric = 0.0
    code = (currency or "PLN").upper()
    suffix = "zł" if code == "PLN" else code
    amount = f"{numeric:,.2f}".replace(",", " ").replace(".", ",")
    return f"{amount} {suffix}"


def _format_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return parsed.strftime("%d.%m.%Y")


def _format_period(period: dict[str, str]) -> str:
    return f"{_format_date(period['start'])}–{_format_date(period['end'])}"


def _transaction_count(value: int | float | None) -> str:
    count = int(value or 0)
    last_two = count % 100
    last = count % 10
    if last == 1 and last_two != 11:
        label = "transakcja"
    elif 2 <= last <= 4 and not 12 <= last_two <= 14:
        label = "transakcje"
    else:
        label = "transakcji"
    return f"{count} {label}"


def _forecast_month(value: str) -> str:
    months = (
        "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
        "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
    )
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return f"{months[parsed.month - 1]} {parsed.year}"


def _priority_label(value: float | None) -> str:
    priority = float(value or 0.0)
    if priority >= 0.75:
        return "wysoki"
    if priority >= 0.5:
        return "średni"
    return "standardowy"


def _category_label(value: str | None) -> str:
    if not value:
        return "(bez kategorii)"
    return _CATEGORY_LABELS_PL.get(value, value)


def _format_get_spending(result: ToolResult) -> str:
    period = result["period"]
    category = (
        _category_label(result.get("category"))
        if result.get("category")
        else "wszystkie kategorie"
    )
    currency = result.get("currency")
    return (
        f"W okresie {_format_period(period)} ({category}) wydatki wyniosły "
        f"{fmt_money(result['total'], currency)} — "
        f"{_transaction_count(result['transactions'])}."
    )


def _format_top_merchants(result: ToolResult) -> str:
    merchants = result.get("merchants") or []
    if not merchants:
        return "Brak danych do top sprzedawców w tym okresie."
    currency = result.get("currency")
    lines = []
    for idx, merchant in enumerate(merchants):
        name = merchant["merchant"] or "(brak nazwy)"
        lines.append(
            f"{idx + 1}. {name} — {fmt_money(merchant['total'], currency)} "
            f"({_transaction_count(merchant['transactions'])})"
        )
    return "Top wydatki:\n" + "\n".join(lines)


def _format_top_categories(result: ToolResult) -> str:
    categories = result.get("categories") or []
    currency = result.get("currency")
    total = float(result.get("total_candidate_spend") or 0.0)
    if not categories and total <= 0:
        return "Brak potwierdzonych wydatków-kandydatów w tym okresie."
    lines = ["Największe potwierdzone kategorie wydatków:"]
    for idx, category in enumerate(categories):
        share = float(category.get("share") or 0.0) * 100.0
        lines.append(
            f"{idx + 1}. {_category_label(category.get('category'))} - "
            f"{fmt_money(category.get('total', 0.0), currency)} "
            f"({share:.1f}%, {_transaction_count(category.get('transactions', 0))})"
        )
    uncategorized = float(result.get("uncategorized_total") or 0.0)
    coverage = float(result.get("category_coverage") or 0.0) * 100.0
    if uncategorized > 0:
        lines.append(
            f"Bez potwierdzonej kategorii: {fmt_money(uncategorized, currency)}. "
            f"Pokrycie kategorii: {coverage:.1f}%."
        )
    return "\n".join(lines)


def _format_cashflow_overview(result: ToolResult) -> str:
    period = result["period"]
    currency = result.get("currency")
    savings_rate = float(result.get("savings_rate") or 0.0) * 100.0
    return (
        f"W okresie {_format_period(period)} wpływy wyniosły "
        f"{fmt_money(result.get('income', 0.0), currency)}, odpływy "
        f"{fmt_money(result.get('expenses', 0.0), currency)}, a bilans "
        f"{fmt_money(result.get('net', 0.0), currency)}. "
        f"Stopa oszczędności: {savings_rate:.1f}% "
        f"({_transaction_count(result.get('transactions', 0))})."
    )


def _format_list_subscriptions(result: ToolResult) -> str:
    subscriptions = result.get("subscriptions") or []
    if not subscriptions:
        return "Nie wykryto subskrypcji."
    currency = result.get("base_currency")
    lines = []
    for sub in subscriptions:
        cadence = _CADENCE_LABELS_PL.get(sub.get("cadence"), sub.get("cadence"))
        lines.append(
            f"- {sub['merchant']} — około "
            f"{fmt_money(sub.get('estimated_monthly_cost'), currency)} miesięcznie "
            f"({cadence})"
        )
    cost = result.get("estimated_monthly_cost", 0.0)
    return (
        f"Wykryte opłaty cykliczne: około {fmt_money(cost, currency)} miesięcznie.\n"
        + "\n".join(lines)
    )


def _format_list_anomalies(result: ToolResult) -> str:
    anomalies = result.get("anomalies") or []
    if not anomalies:
        return "Brak anomalii w tym okresie."
    lines = ["Transakcje wymagające sprawdzenia:"]
    for anomaly in anomalies:
        reasons = anomaly.get("reasons") or []
        reasons_text = f" — {', '.join(reasons)}" if reasons else ""
        lines.append(
            f"- {_format_date(anomaly['booking_date'])} {anomaly['merchant']}: "
            f"{fmt_money(anomaly['amount'], anomaly.get('base_currency'))} "
            f"(priorytet {_priority_label(anomaly.get('priority_score'))})"
            f"{reasons_text}"
        )
    return "\n".join(lines)


def _format_forecast_for(result: ToolResult) -> str:
    error = result.get("error")
    if error == "no_data":
        return "Brak danych do prognozy."
    if error == "insufficient_data":
        return (
            "Za mało danych do wiarygodnej prognozy. "
            f"Dostępne: {result.get('history_months', 0)} z "
            f"{result.get('required_history_months', 0)} wymaganych pełnych miesięcy "
            f"oraz {result.get('active_months', 0)} z "
            f"{result.get('required_active_months', 0)} miesięcy z wydatkami."
        )
    if error:
        return "Nie udało się przygotować prognozy."
    category = (
        _category_label(result.get("category"))
        if result.get("category")
        else "wszystkie wydatki"
    )
    currency = result.get("base_currency")
    lines = [
        f"- {_forecast_month(point['month'])}: "
        f"{fmt_money(point['amount'], currency)}"
        for point in result["forecast"]
    ]
    model_key = str(result.get("model") or "")
    model = _FORECAST_MODEL_LABELS_PL.get(model_key, model_key)
    return f"Orientacyjna prognoza — {category} ({model}):\n" + "\n".join(lines)


def _format_compare_periods(result: ToolResult) -> str:
    a, b = result["a"], result["b"]
    currency = result.get("currency")
    delta_pct = result.get("delta_pct")
    pct = f" ({delta_pct:+.1f}%)" if delta_pct is not None else ""
    return (
        f"Okres A {_format_period(a)}: {fmt_money(a['total'], currency)}.\n"
        f"Okres B {_format_period(b)}: {fmt_money(b['total'], currency)}.\n"
        f"Różnica: {fmt_money(result['delta'], currency)}{pct}."
    )


def _format_recommend_savings(result: ToolResult) -> str:
    opportunities = result.get("category_opportunities") or []
    merchants = result.get("top_merchants") or []
    currency = result.get("base_currency")
    lines = [
        "Najważniejsze miejsca do sprawdzenia:",
        (
            f"- Łączne wydatki: {fmt_money(result.get('total_current', 0.0), currency)} "
            f"(zmiana {fmt_money(result.get('delta', 0.0), currency)})."
        ),
    ]
    lines.append(
        f"- Dochody: {fmt_money(result.get('income', 0.0), currency)}; "
        f"różnica po wydatkach: {fmt_money(result.get('actual_savings', 0.0), currency)}."
    )
    for item in opportunities[:3]:
        pct = item.get("delta_pct")
        pct_text = f", {pct:+.1f}%" if pct is not None else ""
        lines.append(
            f"- Kategoria {_category_label(item['category'])}: wzrost o "
            f"{fmt_money(item['delta'], currency)}{pct_text}."
        )
    if merchants:
        top = merchants[0]
        lines.append(
            f"- Największy odbiorca: {top['merchant']} "
            f"({fmt_money(top['total'], currency)}, "
            f"{_transaction_count(top['transactions'])})."
        )
    subs = result.get("subscriptions") or {}
    if subs.get("count"):
        lines.append(
            f"- Subskrypcje: {subs['count']} pozycji, około "
            f"{fmt_money(subs.get('estimated_monthly_cost', 0.0), currency)} miesięcznie."
        )
    anomalies = result.get("anomalies") or {}
    if anomalies.get("count"):
        lines.append(f"- Nietypowe transakcje do sprawdzenia: {anomalies['count']}.")
    return "\n".join(lines)


def _format_category_review_summary(result: ToolResult) -> str:
    lines = [
        "Kolejka kategoryzacji:",
        f"- Bez kategorii: {result.get('total_uncategorized', 0)}.",
        f"- Bez sugestii: {result.get('without_suggestion', 0)}.",
        (
            f"- Sugestie o niskiej pewności (< {result.get('threshold', 0.55):.2f}): "
            f"{result.get('low_confidence', 0)}."
        ),
        (
            f"- Sugestie o wysokiej pewności (≥ {result.get('accept_threshold', 0.75):.2f}): "
            f"{result.get('high_confidence', 0)}."
        ),
    ]
    categories = result.get("by_predicted_category") or []
    if categories:
        summary = ", ".join(f"{item['category']}: {item['count']}" for item in categories[:5])
        lines.append(f"- Sugestie wg kategorii: {summary}.")
    if result.get("rejected"):
        lines.append(f"- Odrzucone sugestie: {result['rejected']}.")
    lines.append(str(result.get("next_action") or "Sprawdź widok Do przypisania."))
    return "\n".join(lines)


_FORMATTERS: dict[str, Formatter] = {
    "get_spending": _format_get_spending,
    "top_merchants": _format_top_merchants,
    "top_categories": _format_top_categories,
    "cashflow_overview": _format_cashflow_overview,
    "list_subscriptions": _format_list_subscriptions,
    "list_anomalies": _format_list_anomalies,
    "forecast_for": _format_forecast_for,
    "compare_periods": _format_compare_periods,
    "recommend_savings": _format_recommend_savings,
    "category_review_summary": _format_category_review_summary,
}


def format_answer(tool: str, result: ToolResult) -> str:
    """Build a Polish answer from tool output when LLM polishing is disabled."""
    formatter = _FORMATTERS.get(tool)
    if formatter is not None:
        return formatter(result)
    return json.dumps(result, ensure_ascii=False, default=str)
