# Personal Finance App

Self-hosted personal finance analysis app. The project combines bank transaction
imports, a production web dashboard, classical ML models and a local LLM
assistant backed by deterministic domain tools.

## Key Features

- CSV/XLSX imports from Pekao, Revolut or a generic file with manual column mapping.
- Transaction table with filters, category/type editing, tags and notes.
- Separate `transaction_type` semantics from budget expense categories.
- Dashboard with KPIs, cash flow, categories, top merchants and net worth.
- ML suggestions for expense categories using TF-IDF and linear models.
- Rule-based `transaction_type` suggestions with explicit user confirmation.
- Expense forecasting with simple time-series models: naive, mean, SES and ARIMA.
- Anomaly detection with IsolationForest, deterministic rules and user feedback.
- Subscription detection based on payment cadence and amount stability.
- Local LLM assistant: answers are in Polish, but numeric facts come from backend tools.

## Stack

- Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL.
- Frontend: Next.js, React, TypeScript, Tailwind, TanStack Query, Recharts.
- ML: pandas, scikit-learn, statsmodels.
- LLM: local Ollama, optional.
- Runtime: Docker Compose.

## Current Development Status

This repository is an in-progress thesis project prepared for preliminary
review. Transaction import, editing, analytics, the dashboard and the
classification lifecycle are operational. No private transactions or trained
model are bundled with the project.

On a clean database the ML screen intentionally reports that no active model is
available. Category training becomes available after collecting at least 300
explicitly confirmed labels and enough class support to construct valid
validation splits. Model activation is always manual. The private frozen thesis
test remains implemented in the backend but is intentionally hidden from the UI
until the final evaluation stage.

Forecasting, anomaly detection, subscription detection and the
`transaction_type` experiment are useful working modules, but their thesis
evidence status remains explicitly provisional.

## Quick Start

Requirements:

- Docker Desktop
- Python 3.12 and uv for local backend development
- Optional Ollama, if you want to use the LLM assistant

```powershell
copy .env.example .env
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml up -d --build
```

URLs:

- Web app: <http://localhost:3000>
- Swagger API: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

Stop without deleting the database:

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml down
```

Do not use `down -v` unless you intentionally want to delete the PostgreSQL
volume.

## Configuration

Main `.env` variables:

```ini
AUTH_USERNAME=
AUTH_PASSWORD=
DATABASE_URL=postgresql+psycopg://finance:finance@localhost:5432/finance
OLLAMA_BASE_URL=http://localhost:11434
LLM_ENABLED=true
LLM_FALLBACK_ENABLED=false
SCHEDULER_ENABLED=false
```

Set `AUTH_USERNAME` and `AUTH_PASSWORD` to enable BasicAuth. Ollama runs outside
Compose on the host machine.

## Development

Backend:

```powershell
py -3.12 -m pip install uv==0.8.15
uv sync --frozen --extra dev
$env:PYTHONPATH="$PWD\src"
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --port 8000
```

For a local (non-Compose) backend, create `.env` first and set `DATABASE_URL`
to credentials accepted by your PostgreSQL instance. Verify
`http://localhost:8000/health/ready` before starting the frontend.

Frontend:

```powershell
cd apps/web
npm ci
npm run dev
```

Checks:

```powershell
uv run pytest
uv run ruff check .
cd apps/web
npm run typecheck
npm run lint
npm run build
cd ..\..
docker compose -f docker/docker-compose.yml config
```

## ML And Evidence

The project has two classification layers:

- `category` - the budget expense category, for example food, transport, health.
- `transaction_type` - the money-flow semantics, for example expense, salary,
  refund or own transfer.

At runtime, bank/system rules create transaction-type suggestions only.
The ordinary debit/credit fallback is used silently and does not enter the
review queue. A user-created personal rule may still explicitly auto-apply a
type. Only manual decisions and accepted suggestions are training labels; the
transaction-type model remains an evidence-only experiment and is not used by
runtime classification.

Build evidence reports:

```powershell
uv run python scripts\build_ml_evidence.py --from-db
uv run python scripts\inspect_report.py --profile classification-strict
```

Category training uses only explicitly confirmed 9-class expense labels.
`POST /ml/retrain` creates versioned candidates; it never overwrites the active
model. Review gates and activate or roll back a compatible version from the ML
screen. Bank/system categories and model/LLM output remain suggestions until
the user accepts them.

Routine retraining evaluates Logistic Regression with the baseline feature
set. The broader research matrix is added explicitly with
`POST /ml/retrain?include_benchmarks=true`. The database model registry is the
runtime source of truth; JSON reports are evidence outputs and never select the
active artifact.

Reports are written to `data/reports/`. Private anomaly review files are written
to `data/private/`. Both directories are ignored by Git.

## Data Privacy

Do not commit:

- bank exports,
- `.env` files,
- reports generated from real data,
- models trained on private data,
- notebooks with outputs,
- caches or build artifacts.

Keep real data locally in `data/raw/`, `data/private/` or outside the repository.
When sending the project as an archive, exclude the entire `data/` directory and
all `.env` files; Git already ignores these paths.

## Repository Layout

```text
apps/api/       FastAPI routers, middleware and scheduler
apps/web/       Next.js dashboard
src/finance/    domain logic, imports, ML, LLM and statistics
alembic/        database migrations
tests/          backend, ML and domain tests
scripts/        evidence and maintenance scripts
docker/         Dockerfiles and docker-compose
docs/           project documentation, model card and demo notes
```

## Documentation

- `docs/project-overview.md` - architecture, scope and main decisions.
- `docs/presentation-notes.md` - demo and presentation talking points.
- `docs/model-card.md` - model description, data, metrics and limitations.
- `docs/ml-evidence.md` - evidence report generation rules.
- `docs/demo-runbook.md` - clean-start demo workflow.

## License

Code is licensed under the MIT License. Training data, bank exports and local
model artifacts are private and are not part of the license grant.
