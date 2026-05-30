---
name: llm-router-change
description: Use when changing the Polish finance assistant, deterministic routing, Ollama client/fallback, tool schemas, tool implementations, answer formatting, period parsing, prompt behavior, RAG-like behavior, or tests for numeric financial questions and recommendations.
---

# LLM Router Change

Keep the assistant hybrid: deterministic tools first, LLM only for selection, wording, or fallback.

Inspect first:

1. `src/finance/llm/heuristics.py`, `periods.py`, `tool_schemas.py`, `tools.py`.
2. Tool implementations: `spending_tools.py`, `recommendation_tools.py`, `insight_tools.py`, `review_tools.py`, `tool_data.py`.
3. `src/finance/llm/formatters.py`, `router.py`, `client.py`.
4. API surface: `apps/api/routers/chat.py`.
5. Tests: `tests/llm/test_router.py`, `test_tools.py`, `test_periods_formatters.py`, `tests/api/test_llm_fallback.py`.

Rules:

1. Numeric financial questions must route to tools/functions/API, not vector search.
2. The LLM may explain, summarize, polish and recommend.
3. The LLM must not invent amounts, categories, dates or transaction counts.
4. Polish queries should be handled explicitly.
5. Relative periods must be testable with injected dates where possible.
6. Add tests for routing, tool args, formatting, and fallback behavior.

Classify user questions as:

- aggregation,
- comparison,
- forecast,
- anomaly/subscription,
- recommendation,
- documentation/explanation,
- mixed.

For each changed route, document:

- example user query,
- selected tool/function,
- expected args,
- expected answer shape,
- fallback behavior,
- privacy/data-source notes if raw transactions are involved.

Validate with:

- `pytest tests/llm`
- `pytest tests/api/test_llm_fallback.py`
- `ruff check .` when prompts, schemas, or tool code change.
