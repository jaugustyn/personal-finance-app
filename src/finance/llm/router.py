"""Hybrid assistant router: deterministic heuristics first, LLM tool-calling fallback.

Goal: minimise Ollama load. ~80% of typical questions ("Ile wydałem...",
"Top sklepy...", "Subskrypcje?") are routed without invoking the model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from finance.llm import client
from finance.llm.formatters import format_answer
from finance.llm.heuristics import ToolCall, heuristic_route, normalize_question_text
from finance.llm.periods import extract_period
from finance.llm.tools import TOOL_SCHEMAS, TOOLS
from finance.llm.types import ToolResult
from finance.observability import get_logger

logger = get_logger("finance.llm.router")

_PERIOD_FOLLOWUP_TOOLS = frozenset(
    {
        "cashflow_overview",
        "get_spending",
        "top_categories",
        "top_merchants",
        "list_anomalies",
        "recommend_savings",
    }
)

FALLBACK_ANSWER = (
    "Nie wiem jak odpowiedzieć na to pytanie. Obsługuję teraz m.in.: "
    "'Ile wydałem w tym miesiącu?', 'Na co wydaję najwięcej?', "
    "'Gdzie wydałem najwięcej?', 'Jaki mam cashflow w tym miesiącu?', "
    "'Jakie mam subskrypcje?', 'Anomalie?', 'Co mogę ograniczyć?'."
)

# ---------------------------------------------------------------------------
# LLM fallback (tool-calling)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Jesteś routerem lokalnego asystenta finansowego. "
    "Jeżeli pytanie dotyczy danych dostępnych w aplikacji, wybierz dokładnie jedno "
    "pasujące narzędzie. Nie odpowiadaj samodzielnie i nie zgaduj liczb."
)

TOOL_ERROR_ANSWER = (
    "Nie udało się teraz odczytać wymaganych danych. Spróbuj ponownie za chwilę."
)


def _llm_pick_tool(question: str) -> ToolCall | None:
    if not client.is_available():
        return None
    try:
        msg = client.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            tools=TOOL_SCHEMAS,
        )
    except client.OllamaUnavailable:
        logger.warning("ollama_tool_selection_unavailable")
        return None

    if not isinstance(msg, dict):
        logger.warning("ollama_tool_selection_invalid", reason="invalid_message")
        return None
    calls = msg.get("tool_calls")
    if calls is None or calls == []:
        return None
    if not isinstance(calls, list) or not isinstance(calls[0], dict):
        logger.warning("ollama_tool_selection_invalid", reason="invalid_tool_calls")
        return None
    fn = calls[0].get("function")
    if not isinstance(fn, dict):
        logger.warning("ollama_tool_selection_invalid", reason="invalid_function")
        return None
    name = fn.get("name")
    if not isinstance(name, str):
        logger.warning("ollama_tool_selection_invalid", reason="invalid_tool_name")
        return None
    raw_args = fn.get("arguments", {})
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            logger.warning("ollama_tool_selection_invalid", reason="invalid_arguments_json")
            return None
    if not isinstance(raw_args, dict):
        logger.warning("ollama_tool_selection_invalid", reason="invalid_arguments")
        return None
    if name in TOOLS:
        return ToolCall(name=name, args=raw_args)
    return None


def _contextual_route(
    question: str,
    *,
    previous_tool: str | None,
    previous_tool_args: dict[str, Any] | None,
) -> ToolCall | None:
    """Handle short follow-ups like "a w kwietniu?" without requiring an LLM."""
    if previous_tool not in _PERIOD_FOLLOWUP_TOOLS:
        return None
    period = extract_period(question)
    if not period:
        return None
    tokens = normalize_question_text(question).split()
    if len(tokens) > 5:
        return None
    args = dict(previous_tool_args or {})
    args["period"] = period
    return ToolCall(previous_tool, args)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ChatResult:
    answer: str
    tool: str | None
    tool_args: dict[str, Any] | None
    data: ToolResult | None
    source: str  # "heuristic" | "context" | "llm" | "smalltalk"


@lru_cache(maxsize=128)
def _cached_route(question_norm: str) -> ToolCall | None:
    return heuristic_route(question_norm)


def answer(
    question: str,
    session: Session,
    *,
    previous_tool: str | None = None,
    previous_tool_args: dict[str, Any] | None = None,
    today: date | None = None,
) -> ChatResult:
    """Main entrypoint.

    Strategy:
      1. Heuristic router → if match, run tool, format answer (no LLM).
      2. Else LLM tool-call → run tool, format answer.
      3. Else smalltalk fallback.

    Ollama may select a read-only tool for an unmatched question, but the final
    answer is always formatted deterministically from the tool result.
    """
    q_norm = " ".join(question.strip().lower().split())
    call = _cached_route(q_norm)
    source = "heuristic"

    if call is None:
        call = _contextual_route(
            question,
            previous_tool=previous_tool,
            previous_tool_args=previous_tool_args,
        )
        source = "context"

    if call is None:
        call = _llm_pick_tool(question)
        source = "llm"

    if call is None:
        return ChatResult(
            answer=FALLBACK_ANSWER,
            tool=None, tool_args=None, data=None, source="smalltalk",
        )

    fn = TOOLS[call.name]
    try:
        data = fn(session, call.args)
    except Exception:  # noqa: BLE001
        logger.exception("llm_tool_execution_failed", tool=call.name)
        return ChatResult(
            answer=TOOL_ERROR_ANSWER,
            tool=call.name, tool_args=call.args, data=None, source=source,
        )

    return ChatResult(
        answer=format_answer(call.name, data),
        tool=call.name,
        tool_args=call.args,
        data=data,
        source=source,
    )
