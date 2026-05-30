---
name: repo-review
description: Use before commits, before handing off substantial work, or after larger changes to review regressions, architecture boundaries, privacy, API/frontend contracts, ML evidence, LLM factuality, missing tests, migrations, docs, and thesis-quality concerns.
---

# Repo Review

Review the current diff as a senior engineer. Keep the review loose but evidence-based: prioritize concrete risks over style notes.

Start with:

1. `git status --short`
2. `git diff --stat`
3. `git diff --check`
4. Focused `git diff -- <paths>` for changed modules.

Check:

1. Does the change respect architecture boundaries?
2. Does it expose private financial data?
3. Are migrations, DTOs, API clients, or frontend types in sync?
4. Are tests missing or too tied to private data?
5. Are ML metrics, evidence reports, or model artifacts affected?
6. Do LLM answers still use deterministic tools for facts?
7. Are docs, README, or thesis evidence updates needed?

Prioritize:

- correctness,
- privacy,
- reproducibility,
- explainability,
- maintainability.

Run focused tests based on touched paths:

- Backend/domain/API: `pytest tests/ingestion tests/transactions tests/api`
- ML: `pytest tests/ml`
- LLM: `pytest tests/llm tests/api/test_llm_fallback.py`
- Frontend: inspect `apps/web/package.json`; run `npm run lint` and available type/build checks.
- Broad checks when warranted: `pytest`, `ruff check .`, `mypy src/finance apps`.

Output:

- blocking issues,
- non-blocking suggestions,
- tests to run,
- thesis/documentation impact.
