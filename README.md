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
- Evidence-only `transaction_type` multiclass experiment on silver labels.
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

## Quick Start

Requirements:

- Docker Desktop
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
SCHEDULER_ENABLED=false
```

Set `AUTH_USERNAME` and `AUTH_PASSWORD` to enable BasicAuth. Ollama runs outside
Compose on the host machine.

## Development

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,augment]"
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload --port 8000
```

Frontend:

```powershell
cd apps/web
npm install
npm run dev
```

Checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
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
- `transaction_type` - the money-flow semantics, for example purchase, salary,
  refund or own transfer.

At runtime, `transaction_type` is still detected by rules. The
`transaction_type` model is an evidence-only experiment on silver labels, used
for ML reporting and comparison.

Build evidence reports:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py --from-db
```

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
notebooks/      README only; .ipynb files are ignored by default
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
