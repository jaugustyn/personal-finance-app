"""Tests for /chat endpoint when Ollama is unavailable.

Ensures graceful degradation: heuristic-matched questions still answer,
unmatched questions return smalltalk fallback (no 5xx).
"""
from datetime import date
from decimal import Decimal

import pytest

from finance.domain.models import Transaction


@pytest.fixture(autouse=True)
def _ollama_down(monkeypatch):
    """Force Ollama to appear offline for these tests."""
    from apps.api.routers import chat as chat_router
    from finance.llm import client as llm_client
    from finance.llm import router as llm_router

    monkeypatch.setattr(llm_client, "is_available", lambda: False)
    monkeypatch.setattr(llm_router.client, "is_available", lambda: False)
    monkeypatch.setattr(chat_router, "ollama_is_available", lambda: False)


def _seed(session) -> None:
    session.add_all(
        [
            Transaction(
                booking_date=date.today(),
                amount=Decimal("-30"),
                currency="PLN",
                direction="debit",
                merchant="Carrefour",
                title="zakupy",
                category="food",
                source="pekao",
                dedup_hash="c-1",
            ),
            Transaction(
                booking_date=date.today(),
                amount=Decimal("-100"),
                currency="PLN",
                direction="debit",
                merchant="Orange",
                title="abonament",
                category="subscriptions",
                source="pekao",
                dedup_hash="c-2",
            ),
        ]
    )
    session.commit()


def test_chat_health_reports_unavailable(client) -> None:
    r = client.get("/chat/health")
    assert r.status_code == 200
    assert r.json()["ollama_available"] is False


def test_heuristic_question_answers_without_ollama(client, db_session) -> None:
    _seed(db_session)
    r = client.post("/chat", json={"question": "Ile wydałem w tym miesiącu?"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "heuristic"
    assert body["tool"] is not None
    assert body["data"] is not None


def test_unmatched_question_returns_smalltalk(client) -> None:
    r = client.post("/chat", json={"question": "Jaka pogoda jutro w Krakowie?"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "smalltalk"
    assert body["tool"] is None
    assert "Nie wiem" in body["answer"] or "Spróbuj" in body["answer"]


def test_use_llm_summary_falls_back_to_deterministic(client, db_session) -> None:
    _seed(db_session)
    r = client.post(
        "/chat",
        json={"question": "Ile wydałem w tym miesiącu?", "use_llm_summary": True},
    )
    assert r.status_code == 200
    # Even though use_llm_summary=True, Ollama is down → deterministic answer used.
    body = r.json()
    assert body["source"] == "heuristic"
    assert isinstance(body["answer"], str) and len(body["answer"]) > 0
