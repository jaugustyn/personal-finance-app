"""Hybrid assistant router: deterministic heuristics first, LLM tool-calling fallback.

Goal: minimise Ollama load. ~80% of typical questions ("Ile wydałem...",
"Top sklepy...", "Subskrypcje?") are routed without invoking the model.
"""
from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

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
    "Jesteś asystentem finansowym. Odpowiadaj wyłącznie po polsku, krótko i konkretnie. "
    "Gdy pytanie dotyczy danych liczbowych z konta (wydatki, subskrypcje, anomalie, prognozy) "
    "WYWOŁAJ jedno z dostępnych narzędzi zamiast zgadywać liczby. "
    "Po otrzymaniu wyniku narzędzia zwróć krótkie podsumowanie w jednym-dwóch zdaniach."
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
        logger.warning("Ollama unavailable during tool selection")
        return None

    calls = msg.get("tool_calls") or []
    if not calls:
        return None
    fn = calls[0].get("function", {})
    name = fn.get("name")
    raw_args = fn.get("arguments", {})
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            raw_args = {}
    if name in TOOLS:
        return ToolCall(name=name, args=dict(raw_args))
    return None


def _llm_summarise(question: str, tool: str, result: ToolResult) -> str | None:
    if not client.is_available():
        return None
    try:
        msg = client.chat(messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {
                "role": "tool",
                "content": json.dumps(result, ensure_ascii=False, default=str),
                "name": tool,
            },
        ])
    except client.OllamaUnavailable:
        return None
    content = msg.get("content")
    return content.strip() if isinstance(content, str) else None


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
    use_llm_summary: bool = False,
    previous_tool: str | None = None,
    previous_tool_args: dict[str, Any] | None = None,
    today: date | None = None,
) -> ChatResult:
    """Main entrypoint.

    Strategy:
      1. Heuristic router → if match, run tool, format answer (no LLM).
      2. Else LLM tool-call → run tool, format answer.
      3. Else smalltalk fallback.

    `use_llm_summary` is opt-in: if True, the LLM rephrases the deterministic
    answer. Off by default to spare CPU.
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
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tool %s failed", call.name)
        return ChatResult(
            answer=f"Błąd narzędzia {call.name}: {exc}",
            tool=call.name, tool_args=call.args, data=None, source=source,
        )

    base = format_answer(call.name, data)
    if use_llm_summary:
        polished = _llm_summarise(question, call.name, data)
        if polished:
            base = polished
    return ChatResult(answer=base, tool=call.name, tool_args=call.args, data=data, source=source)
