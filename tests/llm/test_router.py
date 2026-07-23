"""Tests for heuristic Polish router (no LLM, no DB)."""
import pytest

from finance.llm import router as llm_router
from finance.llm.router import heuristic_route


@pytest.mark.parametrize(
    ("question", "tool", "expected_args"),
    [
        ("Na co wydaję najwięcej?", "top_categories", {}),
        ("Co pochłania mój budżet?", "top_categories", {}),
        ("Gdzie wydałem najwięcej?", "top_merchants", {}),
        ("Ile wydałem na zakupy?", "get_spending", {"category": "shopping"}),
        ("Ile wydałem na zakupy spożywcze?", "get_spending", {"category": "food"}),
        (
            "Ile zarobiłem w tym miesiącu?",
            "cashflow_overview",
            {"period": "this_month"},
        ),
        ("Jakie mam subskrypcje?", "list_subscriptions", {}),
        ("Anomalie w maju 2026", "list_anomalies", {}),
        ("Co mogę ograniczyć?", "recommend_savings", {}),
    ],
)
def test_heuristic_router_golden_set(question, tool, expected_args):
    call = heuristic_route(question)

    assert call is not None
    assert call.name == tool
    for key, value in expected_args.items():
        assert call.args.get(key) == value


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


def test_routes_top_categories_question():
    call = heuristic_route("Na co wydaję najwięcej?")
    assert call is not None and call.name == "top_categories"


def test_routes_budget_structure_question_to_top_categories():
    call = heuristic_route("Co pochłania mój budżet?")
    assert call is not None and call.name == "top_categories"


def test_routes_where_spending_question_to_top_merchants():
    call = heuristic_route("Gdzie wydaję najwięcej?")
    assert call is not None and call.name == "top_merchants"


def test_routes_where_spent_question_with_polish_l_to_top_merchants():
    call = heuristic_route("Gdzie wydałem najwięcej?")
    assert call is not None and call.name == "top_merchants"


def test_routes_cashflow_question():
    call = heuristic_route("Ile zarobiłem w tym miesiącu?")
    assert call is not None and call.name == "cashflow_overview"
    assert call.args.get("period") == "this_month"


def test_routes_shopping_category_without_groceries_collision():
    call = heuristic_route("Ile wydałem na zakupy w kwietniu 2026?")
    assert call is not None and call.name == "get_spending"
    assert call.args.get("category") == "shopping"

    groceries = heuristic_route("Ile wydałem na zakupy spożywcze?")
    assert groceries is not None and groceries.name == "get_spending"
    assert groceries.args.get("category") == "food"


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


def test_routes_travel_as_transport():
    call = heuristic_route("Ile wydałem na podróże i noclegi w maju?")
    assert call is not None and call.name == "get_spending"
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


def test_tool_failure_returns_controlled_message(monkeypatch):
    def _fail(_session, _args):
        raise RuntimeError("private database detail")

    monkeypatch.setitem(llm_router.TOOLS, "get_spending", _fail)

    result = llm_router.answer("Ile wydałem?", object())  # type: ignore[arg-type]

    assert result.answer == llm_router.TOOL_ERROR_ANSWER
    assert "private database detail" not in result.answer


def test_llm_selects_tool_but_does_not_author_answer(monkeypatch):
    monkeypatch.setattr(llm_router.client, "is_available", lambda: True)
    monkeypatch.setattr(
        llm_router.client,
        "chat",
        lambda **_kwargs: {
            "content": "Zmyślona odpowiedź z inną kwotą: 999 EUR",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_spending",
                        "arguments": {"period": "2026-04"},
                    }
                }
            ],
        },
    )
    monkeypatch.setitem(
        llm_router.TOOLS,
        "get_spending",
        lambda _session, _args: {
            "period": {"start": "2026-04-01", "end": "2026-04-30"},
            "category": None,
            "total": 123.0,
            "currency": "EUR",
            "transactions": 2,
        },
    )

    result = llm_router.answer(
        "Przygotuj finansowe zestawienie alfa",
        object(),  # type: ignore[arg-type]
    )

    assert result.source == "llm"
    assert "123,00 EUR" in result.answer
    assert "999 EUR" not in result.answer


@pytest.mark.parametrize(
    "message",
    [
        [],
        {"tool_calls": "not-a-list"},
        {"tool_calls": [{}]},
        {"tool_calls": [{"function": {"name": "get_spending", "arguments": []}}]},
        {
            "tool_calls": [
                {"function": {"name": "get_spending", "arguments": "{invalid"}}
            ]
        },
    ],
)
def test_malformed_ollama_tool_response_uses_controlled_fallback(
    monkeypatch,
    message,
) -> None:
    monkeypatch.setattr(llm_router.client, "is_available", lambda: True)
    monkeypatch.setattr(llm_router.client, "chat", lambda **_kwargs: message)

    result = llm_router.answer(
        "Przygotuj finansowe zestawienie alfa",
        object(),  # type: ignore[arg-type]
    )

    assert result.source == "smalltalk"
    assert result.tool is None
    assert result.answer == llm_router.FALLBACK_ANSWER


def test_ollama_unavailable_during_chat_uses_controlled_fallback(monkeypatch) -> None:
    def unavailable(**_kwargs):
        raise llm_router.client.OllamaUnavailable("invalid response")

    monkeypatch.setattr(llm_router.client, "is_available", lambda: True)
    monkeypatch.setattr(llm_router.client, "chat", unavailable)

    result = llm_router.answer(
        "Przygotuj finansowe zestawienie alfa",
        object(),  # type: ignore[arg-type]
    )

    assert result.source == "smalltalk"
    assert result.answer == llm_router.FALLBACK_ANSWER


def test_year_month_extracted():
    call = heuristic_route("Ile wydałem 2026-04?")
    assert call is not None
    assert call.args.get("period") == "2026-04"
