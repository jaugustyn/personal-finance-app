# Clean-Start Demo Runbook

This runbook describes final project validation on a fresh database. It does
not contain raw data and must never include bank exports.

## 1. Clean Start

Deleting the Docker volume is destructive. Run it only when the current database
can be lost.

```powershell
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml up -d --build
```

The API container runs `alembic upgrade head` on startup, so a fresh database
should include all migrations, including `category_suggestion_rejected`.

Smoke checks:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/transactions
```

If BasicAuth is enabled, use the username and password from `.env`.

## 2. Import And Category Review

1. Open Next.js: <http://localhost:3000>.
2. Go to `/imports`, upload a real bank export and confirm the mapping.
3. Wait a few seconds for background suggestions.
4. Go to `/transactions` -> `Do przypisania`.
5. Check:
   - transaction types (`purchase`, `own_transfer`, `person_transfer`, `salary`,
     `income`, `refund`, `cash_withdrawal`, `bank_fee`, `savings_investment`),
   - `is_transfer` for own transfers,
   - ML suggestions and confidence,
   - accepting/rejecting suggestions.
6. Manually label the training seed. A practical goal is several dozen examples
   per category, and as many as realistically possible for rare classes.

Do not treat `category_predicted` as a training label until the user accepts it
or assigns the category manually.

## 3. Retraining And Reclassification

From API docs or curl:

```powershell
curl -X POST "http://localhost:8000/ml/retrain?estimator=linear_svc"
curl -X POST "http://localhost:8000/ml/reclassify"
```

After reclassification, return to `/transactions` -> `Do przypisania` and check
whether the new suggestions are reasonable. Reject incorrect suggestions instead
of accepting them.

## 4. ML Evidence Package

After labelling and retraining, run locally:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py --from-db
.\.venv\Scripts\python.exe scripts\inspect_report.py --strict
```

If the database uses a different URL:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py `
  --from-db `
  --database-url "postgresql+psycopg://finance:finance@localhost:5432/finance"
```

Then complete the private anomaly review:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py `
  --from-db `
  --review-file data/private/latest_anomaly_review.csv
.\.venv\Scripts\python.exe scripts\inspect_report.py --strict
```

For the thesis and demo, cite only:

- `data/reports/summary.md`,
- `data/reports/latest_classification.json`,
- `data/reports/latest_eda.json`,
- `data/reports/latest_forecasting.json`,
- `data/reports/latest_anomaly_summary.json`,
- `data/reports/privacy_check_latest.json`.

`data/private/latest_anomaly_review.csv` stays local.

## 5. Demo Scenario

Before the demo, make sure the database contains enough signal:

- several months of transactions, ideally 6+ months for basic forecasting,
- several dozen confirmed expense-category labels,
- several transaction types visible in the table (`purchase`, transfers,
  income, fees, etc.),
- at least one detected subscription,
- several anomalies with saved feedback (`Trafne`, `Nietrafne`,
  `Ignoruj odbiorce`),
- forecast should be shown mainly for all categories; individual categories are
  worth showing only when they have regular history.

Recommended flow:

1. Dashboard: KPIs, cash flow, categories and top merchants.
2. Imports: preview, mapping, import result and deduplication.
3. Transactions: transaction type, assignment view, suggestion accept/reject and
   manual category.
4. Data Quality: training-data work queues.
5. ML Models: experiment report, retrain, reclassify and confidence threshold.
6. Forecast: monthly expense forecast and history-length hint.
7. Anomalies: type, priority, reasons and feedback.
8. Subscriptions: monthly cost and confidence.
9. Assistant: ask in Polish, for example `Co moge ograniczyc w kwietniu 2026?`.

## 6. Readiness Criteria

- `ruff check .`, `pytest`, `mypy src/finance apps` pass.
- Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run build` pass.
- `inspect_report.py --strict` reports no missing files and no raw
  merchant/title leaks.
- `linear_svc` beats `dummy_most_frequent`.
- Anomalies have manually completed `precision@20`, or the lack of review is
  explicitly documented.
