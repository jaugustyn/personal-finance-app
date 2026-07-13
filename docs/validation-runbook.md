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
4. Open `Do sprawdzenia` and review transaction types separately from expense
   categories.
5. Accept only correct suggestions; use a manual value when a suggestion is
   wrong.
6. Use `/review` to process repeated cases efficiently.

Manual decisions and accepted suggestions become gold labels. Bank mappings,
system rules and provisional personal-rule assignments do not.

## 3. Category model lifecycle

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

## 4. Evidence validation

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

## 5. Quality checks

Backend:

```powershell
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
```

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
