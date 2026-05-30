"""Tests for heuristic Polish router (no LLM, no DB)."""
from finance.llm.router import heuristic_route


def test_routes_subscriptions():
    call = heuristic_route("Pokaż moje subskrypcje")
    assert call is not None and call.name == "list_subscriptions"


def test_routes_anomalies_with_period():
    call = heuristic_route("Jakie są anomalie w marcu 2026?")
    assert call is not None and call.name == "list_anomalies"
    assert "marc" in (call.args.get("period") or "")


def test_routes_top_merchants_category():
    call = heuristic_route("Top sklepy spożywcze w tym miesiącu")
    assert call is not None and call.name == "top_merchants"
    assert call.args.get("period") == "this_month"
    assert call.args.get("category") == "food"


def test_routes_spending_health_with_polish_month():
    call = heuristic_route("Ile wydałem na zdrowie w styczniu 2026?")
    assert call is not None and call.name == "get_spending"
    assert call.args.get("category") == "health"
    assert "stycz" in (call.args.get("period") or "")


def test_routes_compare_month_names_without_year():
    call = heuristic_route("Porównaj marzec z kwietniem")
    assert call is not None and call.name == "compare_periods"
    assert call.args.get("period_a") == "marz"
    assert call.args.get("period_b") == "kwiet"


def test_routes_get_spending():
    call = heuristic_route("Ile wydałem w kwietniu 2026?")
    assert call is not None and call.name == "get_spending"
    assert "kwiet" in (call.args.get("period") or "")


def test_routes_forecast():
    call = heuristic_route("Prognoza wydatków na transport")
    assert call is not None and call.name == "forecast_for"
    assert call.args.get("category") == "transport"


def test_routes_savings_recommendations():
    call = heuristic_route("Co mogę ograniczyć w kwietniu 2026?")
    assert call is not None and call.name == "recommend_savings"
    assert "kwiet" in (call.args.get("period") or "")


def test_routes_profile_budget_questions_to_recommendations():
    call = heuristic_route("Czy przekroczyłem limity budżetu w styczniu 2026?")
    assert call is not None and call.name == "recommend_savings"
    assert "stycz" in (call.args.get("period") or "")


def test_routes_category_review_questions():
    call = heuristic_route("Co wymaga review w kategoryzacji i sugestiach?")
    assert call is not None and call.name == "category_review_summary"
    assert call.args.get("threshold") == 0.55


def test_routes_compare():
    call = heuristic_route("Porównaj ten miesiąc z poprzednim")
    assert call is not None and call.name == "compare_periods"


def test_unknown_returns_none():
    call = heuristic_route("Cześć, jak się masz?")
    assert call is None


def test_year_month_extracted():
    call = heuristic_route("Ile wydałem 2026-04?")
    assert call is not None
    assert call.args.get("period") == "2026-04"
