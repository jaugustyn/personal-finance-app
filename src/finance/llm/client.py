"""Thin Ollama HTTP client (chat + tool-calling).

Uses Ollama's OpenAI-compatible /api/chat endpoint. Defaults are tuned for
small CPUs / low VRAM: short context, low num_predict, no streaming.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from finance.config import get_settings

logger = logging.getLogger(__name__)


class OllamaUnavailable(RuntimeError):
    """Raised when Ollama is unreachable or returns a non-2xx response."""


ALLOWED_OLLAMA_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def validated_base_url() -> str:
    """Return a local-only Ollama URL or reject the configuration."""
    raw = get_settings().ollama_base_url.rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_OLLAMA_HOSTS:
        raise OllamaUnavailable(
            "Ollama must run locally on localhost, loopback or host.docker.internal."
        )
    if parsed.username or parsed.password:
        raise OllamaUnavailable("Credentials are not allowed in OLLAMA_BASE_URL.")
    return raw


def _options() -> dict[str, Any]:
    s = get_settings()
    return {
        "num_ctx": s.ollama_num_ctx,
        "num_predict": s.ollama_num_predict,
        "temperature": 0.2,
    }


def is_available() -> bool:
    """Cheap health probe (does not load the model)."""
    s = get_settings()
    if not s.llm_enabled:
        return False
    try:
        r = httpx.get(f"{validated_base_url()}/api/tags", timeout=2.0)
        return r.status_code == 200
    except (httpx.HTTPError, OllamaUnavailable):
        return False


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call Ollama /api/chat. Returns the parsed `message` object.

    Response shape (when tools are used):
        {"role": "assistant", "content": "...", "tool_calls": [{"function": {...}}]}
    """
    s = get_settings()
    base_url = validated_base_url()
    payload: dict[str, Any] = {
        "model": s.ollama_model,
        "messages": messages,
        "stream": False,
        "options": _options(),
    }
    if tools:
        payload["tools"] = tools
    try:
        r = httpx.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=s.ollama_timeout_s,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"Ollama request failed: {exc}") from exc

    data = r.json()
    msg = data.get("message", {})
    if isinstance(msg.get("content"), str) and msg["content"].startswith("{"):
        # Some models put tool_calls inside content as JSON; try to parse.
        try:
            parsed = json.loads(msg["content"])
            if isinstance(parsed, dict) and "name" in parsed:
                msg.setdefault("tool_calls", []).append({"function": parsed})
        except json.JSONDecodeError:
            pass
    return msg


def model_manifest() -> dict[str, Any]:
    """Return exact local Ollama model identity without exposing transaction data."""
    s = get_settings()
    base_url = validated_base_url()
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"Could not inspect local Ollama model: {exc}") from exc
    models = response.json().get("models", [])
    selected: dict[str, Any] = next(
        (
            model
            for model in models
            if model.get("name") == s.ollama_model or model.get("model") == s.ollama_model
        ),
        {},
    )
    return {
        "tag": s.ollama_model,
        "digest": selected.get("digest"),
        "modified_at": selected.get("modified_at"),
        "size": selected.get("size"),
        "details": selected.get("details", {}),
        "options": _options(),
        "base_host": urlparse(base_url).hostname,
    }
