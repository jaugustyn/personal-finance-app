# AGENTS.md

## Project context

This is a self-hosted personal finance analysis system using:

- FastAPI backend in `apps/api`
- Next.js production dashboard in `apps/web`
- core Python package in `src/finance`
- Postgres database
- ML pipelines for classification, forecasting, anomalies and subscriptions
- local LLM assistant with Polish router and Ollama fallback

The project is in quality-hardening mode. Do not rewrite working modules from scratch unless explicitly asked.

## Main architecture boundaries

Respect these boundaries:

- `apps/api/` should contain thin FastAPI routers and API orchestration.
- `apps/web/` should contain production frontend code.
- `src/finance/ingestion/` handles bank import/parsing.
- `src/finance/domain/` owns SQLAlchemy models, enums and DTOs.
- `src/finance/ml/` contains classification, forecasting, anomaly and subscription logic.
- `src/finance/llm/` contains Ollama client, Polish router and tool functions.
- `tests/` should use synthetic or anonymized data.

Do not move logic between layers unless the change is explicitly architectural.

## Privacy rules

- Never commit real bank exports.
- Never print full raw transaction datasets.
- Never expose `.env`, credentials, account numbers or raw private CSV/XLSX contents.
- Treat `data/raw/`, `data/private/`, `data/reports/`, `data/models/` as local/runtime artifacts.
- Use synthetic or anonymized fixtures in tests and examples.
- Do not send private financial data to external APIs.

## Data model rules

The transaction model is still evolving, so changes must be conservative.

Before modifying transaction/domain models:

1. Inspect `src/finance/domain/models.py`.
2. Inspect related API schemas/DTOs.
3. Check ingestion parsers.
4. Check ML feature builders.
5. Check frontend assumptions.
6. Add or update tests.

Do not change category taxonomy, `transaction_type`, `is_transfer`, amount semantics, or date semantics without documenting migration impact.

## ML rules

For classification:

- Keep TF-IDF + LinearSVC baseline reproducible.
- Report macro-F1, weighted-F1 and confusion matrix when changing training logic.
- Avoid data leakage from manual labels, predicted labels or bank-provided categories.
- Preserve confidence diagnostics and optional LLM fallback behavior.

For forecasting:

- Preserve simple baselines.
- Do not replace current model selection with a more complex model without comparison.
- Report evaluation impact.

For anomaly/subscription logic:

- Prefer explainable heuristics and regression tests.
- Do not optimize only for one private dataset.

## LLM assistant rules

The LLM is not the source of truth for financial facts.

For numeric questions:

- use deterministic tools, SQL, aggregation functions or API endpoints,
- then let the LLM explain the result.

For recommendations:

- compute facts first,
- then generate interpretation and suggestions.

RAG/vector search is acceptable for documentation, category explanations and user notes, not for hard financial aggregation.

## Commands

Use these commands where relevant:

```powershell
pytest
ruff check .
mypy src/finance apps
```

Frontend:

```powershell
cd apps/web
npm run lint
npm run typecheck
```

If exact frontend scripts differ, inspect apps/web/package.json first.

Run API locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload --port 8000
```

Docker:

```powershell
docker compose -f docker/docker-compose.yml up -d
```

## Definition of done

For backend changes:

- relevant tests pass,
- API behavior is preserved or documented,
- no private data is exposed.

For frontend changes:

- TypeScript/lint passes where available,
- loading/error/empty states are preserved,
- financial values are formatted consistently.

For ML changes:

- metrics are reported,
- baseline comparison is preserved,
- reproducibility is not weakened.

For LLM changes:

- factual answers use tools/functions,
- prompts do not invent amounts, dates or categories,
- Polish query behavior is tested where relevant.
- Response format

After making changes, summarize:

- changed files,
- what changed,
- commands/tests run,
- known risks,
- recommended next steps.
