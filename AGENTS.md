# AGENTS.md

## Project Context

Self-hosted personal finance analysis app:

- FastAPI backend: `apps/api`
- Next.js dashboard: `apps/web`
- core package: `src/finance`
- PostgreSQL database
- ML: category classification, transaction type evidence, forecasting,
  anomalies, subscriptions
- LLM: local Ollama with Polish routing and deterministic tools

The project is in quality-hardening mode. Do not rewrite working modules from
scratch unless explicitly asked.

## Boundaries

- Keep API routers thin; put domain logic in `src/finance`.
- Keep ingestion/parsing in `src/finance/ingestion`.
- Keep SQLAlchemy models, enums and DTOs in `src/finance/domain`.
- Keep ML logic in `src/finance/ml`.
- Keep LLM routing/tools in `src/finance/llm`.
- Use synthetic or anonymized data in tests.
- Do not move logic across layers unless the task is explicitly architectural.

## Privacy

- Never commit real bank exports, `.env` files, credentials, account numbers or
  raw private CSV/XLSX contents.
- Treat `data/raw/`, `data/private/`, `data/reports/`, `data/models/` and
  `data/external/` as local/runtime artifacts.
- Do not print full raw transaction datasets.
- Do not send private financial data to external APIs.

## Data Model

Before changing transaction/domain models, inspect:

1. `src/finance/domain/models.py`
2. related API schemas/DTOs
3. ingestion parsers
4. ML feature builders
5. frontend assumptions

Do not change category taxonomy, `transaction_type`, `is_transfer`, amount
semantics or date semantics without documenting migration impact and updating
tests.

## Frontend

- Inspect `apps/web/package.json` before assuming scripts or library versions.
- The app uses a recent Next.js version; verify current local package behavior
  for framework-specific changes.
- Preserve loading, error and empty states.
- Keep financial values formatted consistently.
- UI text is intentionally Polish; do not translate runtime UI unless asked.

## ML

- Keep the TF-IDF + LinearSVC baseline reproducible.
- Report macro-F1, weighted-F1 and confusion matrix when changing training
  logic.
- Avoid leakage from manual labels, predicted labels or bank-provided
  categories.
- Preserve confidence diagnostics and optional LLM fallback behavior.
- Preserve simple forecasting baselines unless a comparison justifies replacing
  them.
- Prefer explainable anomaly/subscription heuristics and regression tests.
- Do not optimize only for one private dataset.

## LLM

The LLM is not the source of truth for financial facts.

- Numeric answers must use deterministic tools, SQL, aggregation functions or
  API endpoints first.
- Recommendations must compute facts first, then generate interpretation.
- RAG/vector search is acceptable for documentation, category explanations and
  user notes, not for hard financial aggregation.
- Polish query behavior should be tested when changed.

## Agent Tooling

- Keep one root `AGENTS.md` unless a subproject truly needs different rules.
- Do not commit personal MCP configs, local agent state, credentials or
  IDE-specific agent files.
- Prefer normal repo assets first: scripts, tests, docs and package commands.
- Add repo-local hooks only when lightweight, documented and optional; required
  validation should live in tests/CI, not hooks.
- Custom skills are not needed yet. Add one only for a repeated project workflow
  that cannot be captured clearly in this file or a script.

## Commands

Backend:

```powershell
python -m pytest
python -m ruff check .
python -m mypy src/finance apps
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload --port 8000
```

Frontend:

```powershell
cd apps/web
npm run lint
npm run typecheck
```

Docker:

```powershell
docker compose -f docker/docker-compose.yml up -d
```

## Definition Of Done

- Backend: relevant tests pass, API behavior is preserved or documented, no
  private data is exposed.
- Frontend: TypeScript/lint passes where available, states are preserved,
  financial formatting stays consistent.
- ML: metrics are reported, baseline comparison is preserved, reproducibility is
  not weakened.
- LLM: factual answers use tools/functions and prompts do not invent amounts,
  dates or categories.

## Response Format

After changes, summarize changed files, what changed, commands/tests run, known
risks and recommended next steps.
