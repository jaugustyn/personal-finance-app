"""Deterministic Polish answer formatters for LLM tool results."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

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

Formatter = Callable[[dict[str, Any]], str]


def fmt_money(value: float) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return f"{numeric:,.2f} zł".replace(",", " ").replace(".", ",")


def _category_label(value: str | None) -> str:
    if not value:
        return "(bez kategorii)"
    return _CATEGORY_LABELS_PL.get(value, value)


def _format_get_spending(result: dict[str, Any]) -> str:
    period = result["period"]
    category = result.get("category") or "wszystkie kategorie"
    return (
        f"W okresie {period['start']} - {period['end']} ({category}) wydałeś "
        f"{fmt_money(result['total'])} w {result['transactions']} transakcjach."
    )


def _format_top_merchants(result: dict[str, Any]) -> str:
    merchants = result.get("merchants") or []
    if not merchants:
        return "Brak danych do top sprzedawców w tym okresie."
    lines = []
    for idx, merchant in enumerate(merchants):
        name = merchant["merchant"] or "(brak nazwy)"
        lines.append(
            f"{idx + 1}. {name} - {fmt_money(merchant['total'])} "
            f"({merchant['transactions']} tx)"
        )
    return "Top wydatki:\n" + "\n".join(lines)


def _format_top_categories(result: dict[str, Any]) -> str:
    categories = result.get("categories") or []
    total = float(result.get("total_candidate_spend") or 0.0)
    if not categories and total <= 0:
        return "Brak potwierdzonych wydatków-kandydatów w tym okresie."
    lines = ["Największe potwierdzone kategorie wydatków:"]
    for idx, category in enumerate(categories):
        share = float(category.get("share") or 0.0) * 100.0
        lines.append(
            f"{idx + 1}. {_category_label(category.get('category'))} - "
            f"{fmt_money(category.get('total', 0.0))} "
            f"({share:.1f}%, {category.get('transactions', 0)} tx)"
        )
    uncategorized = float(result.get("uncategorized_total") or 0.0)
    coverage = float(result.get("category_coverage") or 0.0) * 100.0
    if uncategorized > 0:
        lines.append(
            f"Bez potwierdzonej kategorii: {fmt_money(uncategorized)}. "
            f"Pokrycie kategorii: {coverage:.1f}%."
        )
    return "\n".join(lines)


def _format_cashflow_overview(result: dict[str, Any]) -> str:
    period = result["period"]
    savings_rate = float(result.get("savings_rate") or 0.0) * 100.0
    return (
        f"W okresie {period['start']} - {period['end']} przychody wyniosły "
        f"{fmt_money(result.get('income', 0.0))}, wydatki "
        f"{fmt_money(result.get('expenses', 0.0))}, a wynik netto "
        f"{fmt_money(result.get('net', 0.0))}. "
        f"Stopa oszczędności: {savings_rate:.1f}% "
        f"({result.get('transactions', 0)} transakcji)."
    )


def _format_list_subscriptions(result: dict[str, Any]) -> str:
    subscriptions = result.get("subscriptions") or []
    if not subscriptions:
        return "Nie wykryto subskrypcji."
    lines = []
    for sub in subscriptions:
        lines.append(
            f"- {sub['merchant']} ({sub['cadence']}, "
            f"{fmt_money(sub['median_amount'])}, "
            f"zaufanie {sub['confidence']:.2f})"
        )
    cost = result.get("estimated_monthly_cost", 0.0)
    return f"Wykryte subskrypcje (~{fmt_money(cost)} / mies.):\n" + "\n".join(lines)


def _format_list_anomalies(result: dict[str, Any]) -> str:
    anomalies = result.get("anomalies") or []
    if not anomalies:
        return "Brak anomalii w tym okresie."
    lines = []
    for anomaly in anomalies:
        reasons = anomaly.get("reasons") or []
        reasons_text = f" — {', '.join(reasons)}" if reasons else ""
        lines.append(
            f"- {anomaly['booking_date']} {anomaly['merchant']}: "
            f"{fmt_money(anomaly['amount'])} (severity {anomaly['severity']:.2f})"
            f"{reasons_text}"
        )
    return "Anomalie:\n" + "\n".join(lines)


def _format_forecast_for(result: dict[str, Any]) -> str:
    if "error" in result:
        return "Brak danych do prognozy."
    category = result.get("category") or "wszystko"
    lines = [f"- {f['month']}: {fmt_money(f['amount'])}" for f in result["forecast"]]
    mape = result.get("mape")
    suffix = f" (model {result['model']}, MAPE {mape:.1f}%)" if mape is not None else ""
    return f"Prognoza dla {category}{suffix}:\n" + "\n".join(lines)


def _format_compare_periods(result: dict[str, Any]) -> str:
    a, b = result["a"], result["b"]
    delta_pct = result.get("delta_pct")
    pct = f" ({delta_pct:+.1f}%)" if delta_pct is not None else ""
    return (
        f"Okres A {a['start']}-{a['end']}: {fmt_money(a['total'])}.\n"
        f"Okres B {b['start']}-{b['end']}: {fmt_money(b['total'])}.\n"
        f"Różnica: {fmt_money(result['delta'])}{pct}."
    )


def _format_recommend_savings(result: dict[str, Any]) -> str:
    opportunities = result.get("category_opportunities") or []
    merchants = result.get("top_merchants") or []
    lines = [
        "Najważniejsze miejsca do sprawdzenia:",
        (
            f"- Łączne wydatki: {fmt_money(result.get('total_current', 0.0))} "
            f"(zmiana {fmt_money(result.get('delta', 0.0))})."
        ),
    ]
    goal = result.get("savings_goal") or {}
    if goal.get("target") is not None:
        status = "osiągnięty" if goal.get("met") else "jeszcze nieosiągnięty"
        lines.append(
            f"- Cel oszczędnościowy {fmt_money(goal['target'])}: {status}; "
            f"aktualnie {fmt_money(goal.get('actual_savings', 0.0))}."
        )
    for alert in (result.get("category_limit_alerts") or [])[:3]:
        lines.append(
            f"- Limit {alert['category']}: przekroczony o "
            f"{fmt_money(alert.get('over_by', 0.0))}."
        )
    for item in opportunities[:3]:
        pct = item.get("delta_pct")
        pct_text = f", {pct:+.1f}%" if pct is not None else ""
        lines.append(
            f"- Kategoria {item['category']}: wzrost o "
            f"{fmt_money(item['delta'])}{pct_text}."
        )
    if merchants:
        top = merchants[0]
        lines.append(
            f"- Największy odbiorca: {top['merchant']} "
            f"({fmt_money(top['total'])}, {top['transactions']} tx)."
        )
    subs = result.get("subscriptions") or {}
    if subs.get("count"):
        lines.append(
            f"- Subskrypcje: {subs['count']} pozycji, około "
            f"{fmt_money(subs.get('estimated_monthly_cost', 0.0))} / mies."
        )
    anomalies = result.get("anomalies") or {}
    if anomalies.get("count"):
        lines.append(f"- Anomalie do review: {anomalies['count']}.")
    return "\n".join(lines)


def _format_category_review_summary(result: dict[str, Any]) -> str:
    lines = [
        "Kolejka kategoryzacji:",
        f"- Bez kategorii: {result.get('total_uncategorized', 0)}.",
        f"- Bez sugestii: {result.get('without_suggestion', 0)}.",
        (
            f"- Niski confidence < {result.get('threshold', 0.55):.2f}: "
            f"{result.get('low_confidence', 0)}."
        ),
        (
            f"- Wysoki confidence >= {result.get('accept_threshold', 0.75):.2f}: "
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


def format_answer(tool: str, result: dict[str, Any]) -> str:
    """Build a Polish answer from tool output when LLM polishing is disabled."""
    formatter = _FORMATTERS.get(tool)
    if formatter is not None:
        return formatter(result)
    return json.dumps(result, ensure_ascii=False, default=str)
