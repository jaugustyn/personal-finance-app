---
name: data-model-change
description: Use when changing SQLAlchemy/domain models, Alembic migrations, transaction schema or semantics, Category/TransactionType enums, TransactionDTO, ingestion mappings, deduplication, personal rules, API/frontend transaction contracts, or fields such as category, transaction_type, is_transfer, amount, direction, booking_date, booking_datetime.
---

# Data Model Change

Keep data model changes conservative and trace every affected boundary before editing.

Inspect first:

1. `src/finance/domain/models.py`, `src/finance/domain/enums.py`, `src/finance/domain/dto.py`, `src/finance/domain/category_mapping.py`.
2. `alembic/versions/` for existing migration style and historical schema decisions.
3. `src/finance/ingestion/` parsers and `src/finance/transactions/` rules, queries, mutations and services.
4. `apps/api/routers/transactions.py`, `imports.py`, `categories.py`, `profile.py`, `ml.py`.
5. `apps/web/src/lib/api/types.ts`, API clients, and affected dashboard pages/components.
6. Tests in `tests/ingestion/`, `tests/transactions/`, `tests/api/`, `tests/ml/`, `tests/llm/`.

Use this impact search when transaction fields or enums move:

```bash
rg -n "TransactionDTO|Transaction\\(|category|transaction_type|is_transfer|dedup_hash|booking_date|booking_datetime|amount|direction" src apps tests alembic
```

Guardrails:

- Do not change category taxonomy, `transaction_type`, `is_transfer`, amount sign, direction, or date semantics without documenting migration/backfill impact.
- Preserve import deduplication and own-account transfer behavior.
- Keep tests synthetic/anonymized; never print raw bank exports.
- If DB shape changes, add or update an Alembic migration and check downgrade/backfill assumptions.

Validate with focused tests first, then broader checks when risk warrants:

- `pytest tests/ingestion tests/transactions tests/api`
- Add `pytest tests/ml tests/llm` if category/type semantics feed ML or assistant tools.
- Run `ruff check .` and `mypy src/finance apps` for shared contract changes.

Output:

- schema impact,
- migration risk,
- affected modules,
- tests required.
