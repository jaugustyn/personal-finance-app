"""Thin Ollama HTTP client (chat + tool-calling).

Uses Ollama's OpenAI-compatible /api/chat endpoint. Defaults are tuned for
small CPUs / low VRAM: short context, low num_predict, no streaming.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from finance.config import get_settings

logger = logging.getLogger(__name__)


class OllamaUnavailable(RuntimeError):
    """Raised when Ollama is unreachable or returns a non-2xx response."""


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
        r = httpx.get(f"{s.ollama_base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
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
            f"{s.ollama_base_url}/api/chat",
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
