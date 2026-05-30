"""API tests for classifier diagnostics and optional LLM fallback."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np

from finance.ml.classification import predict as predict_mod


class _FakePipeline:
    def __init__(self, *, category: str = "food", confidence: float = 0.8) -> None:
        self.category = category
        self.confidence = confidence

    def predict(self, _x):
        return np.asarray([self.category])

    def predict_proba(self, _x):
        return np.asarray([[self.confidence, 1.0 - self.confidence]])


def _payload(**overrides):
    data = {
        "merchant": "Lidl",
        "title": "zakupy",
        "amount": str(Decimal("-42.10")),
        "booking_date": date(2026, 1, 10).isoformat(),
    }
    data.update(overrides)
    return data


def test_classify_returns_model_diagnostics(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.83))

    response = client.post("/ml/classify", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["model_category"] == "food"
    assert body["confidence"] == 0.83
    assert body["source"] == "model"
    assert body["fallback_used"] is False


def test_classify_low_confidence_does_not_fallback_by_default(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)

    response = client.post("/ml/classify", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["source"] == "model"
    assert body["fallback_used"] is False


def test_classify_uses_valid_llm_fallback_when_enabled(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(
        predict_mod.llm_client,
        "chat",
        lambda **_kwargs: {"content": "transport"},
    )

    response = client.post(
        "/ml/classify",
        json=_payload(use_llm_fallback=True, threshold=0.55),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "transport"
    assert body["model_category"] == "food"
    assert body["source"] == "llm_fallback"
    assert body["fallback_used"] is True


def test_classify_rejects_invalid_llm_category(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(
        predict_mod.llm_client,
        "chat",
        lambda **_kwargs: {"content": "groceries"},
    )

    response = client.post(
        "/ml/classify",
        json=_payload(use_llm_fallback=True, threshold=0.55),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["source"] == "model"
    assert body["fallback_used"] is False
