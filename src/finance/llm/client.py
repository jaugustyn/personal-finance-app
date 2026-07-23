"""Thin Ollama HTTP client (chat + tool-calling).

Uses Ollama's OpenAI-compatible /api/chat endpoint. Defaults are tuned for
small CPUs / low VRAM: short context, low num_predict, no streaming.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

from finance.config import get_settings
from finance.observability import get_logger

logger = get_logger("finance.llm.client")


class OllamaUnavailable(RuntimeError):
    """Raised when Ollama is unreachable or returns an unusable response."""


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
        logger.warning(
            "ollama_chat_unavailable",
            reason="http_error",
            error_type=type(exc).__name__,
        )
        raise OllamaUnavailable("Ollama request failed.") from exc

    data = _json_object(r, operation="chat")
    msg = data.get("message")
    if not isinstance(msg, dict):
        logger.warning("ollama_chat_invalid_response", reason="missing_message")
        raise OllamaUnavailable("Ollama response does not contain a message object.")

    calls = msg.get("tool_calls")
    if calls is None:
        calls = []
    elif not isinstance(calls, list):
        logger.warning("ollama_chat_invalid_response", reason="invalid_tool_calls")
        raise OllamaUnavailable("Ollama returned malformed tool calls.")

    content = msg.get("content")
    if isinstance(content, str) and content.startswith("{"):
        # Some models put tool_calls inside content as JSON; try to parse.
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "name" in parsed:
                calls.append({"function": parsed})
        except json.JSONDecodeError:
            pass
    if calls:
        msg["tool_calls"] = _normalize_tool_calls(calls)
    return msg


def model_manifest() -> dict[str, Any]:
    """Return exact local Ollama model identity without exposing transaction data."""
    s = get_settings()
    base_url = validated_base_url()
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(
            "ollama_manifest_unavailable",
            reason="http_error",
            error_type=type(exc).__name__,
        )
        raise OllamaUnavailable("Could not inspect local Ollama model.") from exc
    data = _json_object(response, operation="manifest")
    models = data.get("models", [])
    if not isinstance(models, list) or not all(isinstance(model, dict) for model in models):
        logger.warning("ollama_manifest_invalid_response", reason="invalid_models")
        raise OllamaUnavailable("Ollama returned a malformed model manifest.")
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


def _json_object(response: httpx.Response, *, operation: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        logger.warning(
            "ollama_invalid_json",
            operation=operation,
            error_type=type(exc).__name__,
        )
        raise OllamaUnavailable("Ollama returned invalid JSON.") from exc
    if not isinstance(data, dict):
        logger.warning("ollama_invalid_json_shape", operation=operation)
        raise OllamaUnavailable("Ollama returned a non-object JSON response.")
    return data


def _normalize_tool_calls(calls: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            logger.warning("ollama_chat_invalid_response", reason="invalid_tool_call")
            raise OllamaUnavailable("Ollama returned malformed tool calls.")
        function = dict(call["function"])
        name = function.get("name")
        if not isinstance(name, str) or not name:
            logger.warning("ollama_chat_invalid_response", reason="invalid_tool_name")
            raise OllamaUnavailable("Ollama returned malformed tool calls.")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                logger.warning("ollama_chat_invalid_response", reason="invalid_tool_arguments")
                raise OllamaUnavailable("Ollama returned malformed tool calls.") from exc
        if not isinstance(arguments, dict):
            logger.warning("ollama_chat_invalid_response", reason="invalid_tool_arguments")
            raise OllamaUnavailable("Ollama returned malformed tool calls.")
        function["arguments"] = arguments
        normalized.append({**call, "function": function})
    return normalized
