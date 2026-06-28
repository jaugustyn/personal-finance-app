# AGENTS.md

## Project Context

Self-hosted personal finance analysis app:

* FastAPI backend: `apps/api`
* Next.js dashboard: `apps/web`
* core package: `src/finance`
* PostgreSQL database
* ML: category classification, transaction type evidence, forecasting,
  anomalies, subscriptions
* LLM: local Ollama with Polish routing and deterministic tools

The project is in quality-hardening mode. Prefer small, focused, low-risk changes over rewrites.

## Work Discipline

* Do not rewrite working modules from scratch unless explicitly asked.
* Touch only code directly related to the task.
* Match existing local style and project structure.
* Do not add features, abstractions, dependencies or configurability unless requested or clearly justified.
* Mention unrelated issues when noticed, but do not fix them unless asked.

## Architecture Boundaries

* Keep API routers thin; put domain logic in `src/finance`.
* Keep ingestion/parsing in `src/finance/ingestion`.
* Keep SQLAlchemy models, enums and DTOs in `src/finance/domain`.
* Keep ML logic in `src/finance/ml`.
* Keep LLM routing/tools in `src/finance/llm`.
* Do not move logic across layers unless the task is explicitly architectural.

## Privacy

* Never commit real bank exports, `.env` files, credentials, account numbers or raw private CSV/XLSX contents.
* Treat `data/raw/`, `data/private/`, `data/reports/`, `data/models/` and `data/external/` as local/runtime artifacts.
* Use synthetic or anonymized data in tests.
* Do not print full raw transaction datasets.
* Do not send private financial data to external APIs.

## Data Model and Database

Before changing transaction/domain models, inspect:

1. `src/finance/domain/models.py`
2. related API schemas/DTOs
3. ingestion parsers
4. ML feature builders
5. frontend assumptions

Rules:

* Consider migrations for SQLAlchemy model changes.
* Do not drop or rename columns without an explicit task requirement.
* Preserve backward compatibility for existing local data when practical.
* If no migration system exists, document required manual schema changes.

## Frontend

* Inspect `apps/web/package.json` before assuming scripts or library versions.
* Preserve loading, error and empty states.
* Keep financial values formatted consistently.
* UI text is intentionally Polish; do not translate runtime UI unless asked.

## ML

* Keep the TF-IDF + LinearSVC baseline reproducible.
* Report macro-F1, weighted-F1 and confusion matrix when changing training logic.
* Avoid leakage from manual labels, predicted labels or bank-provided categories.
* Preserve confidence diagnostics and optional LLM fallback behavior.
* Do not optimize only for one private dataset.

## LLM

The LLM is not the source of truth for financial facts.

* Numeric answers must use deterministic tools, SQL, aggregation functions or API endpoints first.
* Recommendations must compute facts first, then generate interpretation.
* RAG/vector search is acceptable for documentation, category explanations and user notes, not for hard financial aggregation.
* Polish query behavior should be tested when changed.

## Response Format

After changes, summarize changed files, what changed, commands/tests run, known risks and recommended next steps.
