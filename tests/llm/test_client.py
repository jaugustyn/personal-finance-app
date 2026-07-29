"""Ollama response validation tests."""
from __future__ import annotations

import httpx
import pytest

from finance.llm import client


def _response(content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=content,
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


@pytest.mark.parametrize(
    "content",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"message": null}',
        b'{"message": {"tool_calls": "invalid"}}',
        b'{"message": {"tool_calls": [{}]}}',
        (
            b'{"message": {"tool_calls": [{"function": '
            b'{"name": "get_spending", "arguments": []}}]}}'
        ),
    ],
)
def test_chat_rejects_unusable_ollama_responses(monkeypatch, content) -> None:
    monkeypatch.setattr(client, "validated_base_url", lambda: "http://localhost:11434")
    monkeypatch.setattr(client.httpx, "post", lambda *args, **kwargs: _response(content))

    with pytest.raises(client.OllamaUnavailable):
        client.chat([{"role": "user", "content": "redacted"}])


def test_chat_normalizes_json_tool_arguments(monkeypatch) -> None:
    response = _response(
        b'{"message": {"content": "", "tool_calls": [{"function": '
        b'{"name": "get_spending", "arguments": "{\\"period\\": \\"this_month\\"}"}}]}}'
    )
    monkeypatch.setattr(client, "validated_base_url", lambda: "http://localhost:11434")
    monkeypatch.setattr(client.httpx, "post", lambda *args, **kwargs: response)

    message = client.chat([{"role": "user", "content": "redacted"}])

    assert message["tool_calls"][0]["function"]["arguments"] == {
        "period": "this_month"
    }


def test_installed_models_returns_unique_sorted_tags(monkeypatch) -> None:
    response = httpx.Response(
        200,
        json={
            "models": [
                {"name": "qwen:7b"},
                {"model": "llama:8b"},
                {"name": "qwen:7b"},
            ]
        },
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
    )
    monkeypatch.setattr(client, "validated_base_url", lambda: "http://localhost:11434")
    monkeypatch.setattr(client.httpx, "get", lambda *args, **kwargs: response)

    assert client.installed_models() == ["llama:8b", "qwen:7b"]


def test_chat_uses_requested_model(monkeypatch) -> None:
    response = _response(b'{"message": {"content": "ok"}}')
    payload: dict[str, object] = {}

    def _post(*_args, **kwargs):
        payload.update(kwargs["json"])
        return response

    monkeypatch.setattr(client, "validated_base_url", lambda: "http://localhost:11434")
    monkeypatch.setattr(client.httpx, "post", _post)

    client.chat([{"role": "user", "content": "redacted"}], model="qwen:7b")

    assert payload["model"] == "qwen:7b"
