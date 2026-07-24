# Validation Runbook

This runbook covers a clean local start, the data workflow and project quality
checks. Private transaction files and generated model artifacts remain local.

## 1. Start the stack

Create `.env` from the example and start Docker Compose:

```powershell
copy .env.example .env
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml up -d --build
```

Verify:

- web: <http://localhost:3000>;
- API documentation: <http://localhost:8000/docs>;
- readiness: <http://localhost:8000/health/ready>.

The API applies `alembic upgrade head` before startup.

To intentionally remove all local database data:

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml down -v
```

This operation is destructive.

## 2. Import and data verification

1. Open `/imports` and upload a Pekao, Revolut or generic export.
2. Verify the preview, mapping, detected currency and import summary.
3. Open `/transactions` and verify amounts, ordering and merchant names.
   Foreign rows without a PLN conversion should remain visible and be reported
   as omitted from monetary summaries.
4. Open `Do sprawdzenia` and review transaction types separately from expense
   categories.
5. Accept only correct suggestions; use a manual value when a suggestion is
   wrong.

Manual decisions and accepted suggestions become gold labels. Bank mappings,
system rules and provisional personal-rule assignments do not.

## 3. Operational smoke test

Before validating ML, check the main data mutations:

1. Add a manual transaction, edit it and verify that the list and financial
   summary update consistently.
2. Create a fixed-charge schedule, link and unlink an existing transaction,
   then add an explicit manual payment for one occurrence.
3. Add one aggregate asset and one detailed account. Update a valuation,
   archive and restore an item, and verify that a foreign valuation without a
   PLN rate is excluded from the displayed total.
4. In Settings, enable the inactivity lock with a short timeout, lock the
   application manually, unlock it and disable the lock again.

These checks use synthetic values only. A fixed-charge schedule must not create
a transaction until the user explicitly adds a payment.

## 4. Category model lifecycle

The ML screen first reports data readiness. On a clean or insufficiently
labelled database, the missing active model and disabled training action are
correct states.

When readiness is satisfied:

1. Start the default job from `/ml` or `POST /ml/retrain` without estimator
   filters. It evaluates both baseline candidates.
2. Wait for `GET /ml/retrain/status` to return `completed`.
3. Verify both holdouts, technical gates and the recommendation.
4. Manually activate a passing candidate.
5. Run `Przelicz sugestie` or `POST /ml/reclassify`.
6. Inspect the new suggestions in the review queue.

Retraining never activates a model automatically. Suggestions should only be
accepted when they are correct.

## 5. Evidence validation

After a model has been trained and activated:

```powershell
uv run python scripts\build_ml_evidence.py --from-db
uv run python scripts\inspect_report.py --profile classification-strict
```

For anomaly precision, fill the private review file and regenerate:

```powershell
uv run python scripts\build_ml_evidence.py --from-db --review-file data/private/latest_anomaly_review.csv
uv run python scripts\inspect_report.py --profile classification-strict
```

Aggregate outputs are written to `data/reports`. Row-level anomaly review,
model artifacts and database contents remain local.

## 6. Quality checks

Backend:

```powershell
uv run alembic upgrade head
uv run alembic check
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
uv run python scripts\check_data_integrity.py
```

The fast reference financial scenario is part of the regular test suite.
PostgreSQL integration tests are excluded from a plain `pytest` run. Their real
import and deduplication path requires a dedicated database whose name ends
with `_test`:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://finance:finance@localhost:5432/finance_test"
$env:DATABASE_URL=$env:TEST_DATABASE_URL
uv run pytest tests\integration\test_reference_financial_scenario_postgres.py -m postgres_integration --no-cov
```

The integration fixture applies Alembic migrations and clears that test
database. It refuses to run against a database without the `_test` suffix.

Frontend:

```powershell
cd apps/web
npm run typecheck
npm run lint
npm run build
```

Configuration and repository:

```powershell
docker compose -f docker/docker-compose.yml config
git diff --check
git status --short
```

Expected conditions:

- tests and static checks pass;
- Docker Compose configuration is valid;
- only intended source changes are present;
- `.env`, bank exports, generated reports and model artifacts are not tracked;
- modules with incomplete evaluation remain marked as `provisional`.

The integrity command prints aggregate counts and transaction IDs only. Exit
code `0` means no critical inconsistency; exit code `1` means the reported IDs
require review or an explicit currency recomputation.

CI runs the regular backend and frontend suites for every pull request. The
PostgreSQL reference scenario and migration checks remain explicit local
integration checks. Docker images are rebuilt only after Docker or dependency
changes. Dependency security audits run weekly and can also be started
manually.
