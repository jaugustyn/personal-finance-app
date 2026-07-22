from __future__ import annotations

from datetime import date

from finance.llm.formatters import format_answer
from finance.llm.periods import extract_all_periods, extract_period, parse_period


def test_extract_periods_for_polish_months_and_year_month() -> None:
    assert extract_period("Ile wydałem w kwietniu 2026?") == "kwiet 2026"
    assert extract_period("Ile wydałem 2026-04?") == "2026-04"
    assert extract_all_periods("Porównaj 2026-04 z 2026-03") == ["2026-04", "2026-03"]


def test_parse_period_relative_with_injected_today() -> None:
    start, end = parse_period("last_month", today=date(2026, 5, 14))
    assert start == date(2026, 4, 1)
    assert end == date(2026, 4, 30)


def test_format_answer_get_spending_is_deterministic() -> None:
    answer = format_answer(
        "get_spending",
        {
            "period": {"start": "2026-04-01", "end": "2026-04-30"},
            "category": "food",
            "total": 123.45,
            "currency": "EUR",
            "transactions": 3,
        },
    )
    assert "Jedzenie" in answer
    assert "123,45 EUR" in answer
    assert "01.04.2026–30.04.2026" in answer


def test_format_answer_top_categories_is_deterministic() -> None:
    answer = format_answer(
        "top_categories",
        {
            "period": {"start": "2026-04-01", "end": "2026-04-30"},
            "total_candidate_spend": 220.0,
            "categorized_total": 150.0,
            "uncategorized_total": 70.0,
            "category_coverage": 150.0 / 220.0,
            "transactions": 3,
            "categories": [
                {
                    "category": "food",
                    "total": 100.0,
                    "transactions": 1,
                    "share": 100.0 / 220.0,
                }
            ],
        },
    )
    assert "Jedzenie" in answer
    assert "Bez potwierdzonej kategorii" in answer


def test_format_answer_cashflow_overview_is_deterministic() -> None:
    answer = format_answer(
        "cashflow_overview",
        {
            "period": {"start": "2026-04-01", "end": "2026-04-30"},
            "income": 1000.0,
            "gross_expenses": 300.0,
            "refunds": 50.0,
            "expenses": 250.0,
            "debt_payments": 100.0,
            "asset_allocations": 200.0,
            "net": 450.0,
            "savings_rate": 0.65,
            "transactions": 2,
        },
    )
    assert "wpływy" in answer
    assert "450,00 zł" in answer
    assert "zwroty 50,00 zł" in answer


def test_format_answer_recommend_savings_is_deterministic() -> None:
    answer = format_answer(
        "recommend_savings",
        {
            "total_current": 230.0,
            "delta": 130.0,
            "category_opportunities": [
                {
                    "category": "food",
                    "delta": 80.0,
                    "delta_pct": 80.0,
                }
            ],
            "top_merchants": [
                {"merchant": "Market", "total": 180.0, "transactions": 1}
            ],
            "subscriptions": {"count": 0, "estimated_monthly_cost": 0.0},
            "anomalies": {"count": 0},
        },
    )
    assert "230,00 zł" in answer
    assert "Jedzenie" in answer


def test_format_answer_forecast_ignores_empty_error_field() -> None:
    answer = format_answer(
        "forecast_for",
        {
            "category": "food",
            "base_currency": "USD",
            "error": None,
            "model": "naive",
            "mape": None,
            "rmse": None,
            "forecast": [{"month": "2026-08-01", "amount": 123.0}],
        },
    )
    assert "Orientacyjna prognoza" in answer
    assert "Jedzenie" in answer
    assert "sierpień 2026" in answer
    assert "123,00 USD" in answer


def test_format_forecast_explains_missing_history() -> None:
    answer = format_answer(
        "forecast_for",
        {
            "category": None,
            "base_currency": "PLN",
            "error": "insufficient_data",
            "history_months": 8,
            "active_months": 5,
            "required_history_months": 14,
            "required_active_months": 6,
            "forecast": [],
        },
    )

    assert "8 z 14" in answer
    assert "5 z 6" in answer


def test_format_subscriptions_hides_technical_confidence() -> None:
    answer = format_answer(
        "list_subscriptions",
        {
            "base_currency": "EUR",
            "estimated_monthly_cost": 12.5,
            "subscriptions": [
                {
                    "merchant": "Example",
                    "cadence": "monthly",
                    "estimated_monthly_cost": 12.5,
                    "confidence": 0.91,
                }
            ],
        },
    )

    assert "12,50 EUR" in answer
    assert "co miesiąc" in answer
    assert "confidence" not in answer
    assert "zaufanie" not in answer


def test_format_anomalies_uses_priority_instead_of_severity() -> None:
    answer = format_answer(
        "list_anomalies",
        {
            "anomalies": [
                {
                    "booking_date": "2026-04-10",
                    "merchant": "Sklep",
                    "amount": -500.0,
                    "base_currency": "EUR",
                    "priority_score": 0.8,
                    "severity": 0.95,
                    "reasons": ["nietypowa kwota"],
                }
            ]
        },
    )

    assert "10.04.2026" in answer
    assert "500,00 EUR" in answer
    assert "priorytet wysoki" in answer
    assert "severity" not in answer


def test_format_answer_unknown_falls_back_to_json() -> None:
    assert format_answer("unknown", {"ok": True}) == '{"ok": true}'
