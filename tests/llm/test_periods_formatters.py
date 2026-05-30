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
            "transactions": 3,
        },
    )
    assert "food" in answer
    assert "123,45 zł" in answer


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
    assert "food" in answer


def test_format_answer_unknown_falls_back_to_json() -> None:
    assert format_answer("unknown", {"ok": True}) == '{"ok": true}'
