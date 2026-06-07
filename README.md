# Personal Finance Analysis System

Self-hosted system for analyzing and optimizing personal expenses using
FastAPI, Next.js, classical ML and a local LLM.

## Status

Current focus: Phase 12 - personalization and AI/ML quality improvements.

- Phase 1: ingestion (Pekao + Revolut), API, web UI, Docker, CI
- Phase 2: ML categorisation with TF-IDF + linear models and LLM augmentation
- Phase 3: monthly forecasting, IsolationForest anomalies, subscription detector
- Phase 4: hybrid LLM assistant with deterministic tools and Ollama fallback
- Phase 5: BasicAuth, structured logging, scheduler, health checks
- Phase 6: Next.js dashboard for imports, transactions, categories, stats, ML views
- Phase 7+: evidence package, review workflow, transaction type evidence, demo polish

## From Zero To Running

Prerequisites: **Docker Desktop** and optionally **Ollama** running on the host
for the chat assistant.

```powershell
git clone <repo> finance
cd finance
copy .env.example .env
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml up -d --build --force-recreate
```

Then open:

- Web dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

Import a CSV/XLSX file from the Next.js `/imports` page, wait for parsing and
classification, then use the web dashboard for review and analytics.

### Optional: BasicAuth

Set both in `.env`:

```ini
AUTH_USERNAME=admin
AUTH_PASSWORD=change-me
```

`/health` stays public; all other protected endpoints require credentials. The
Next.js proxy attaches server-side credentials when `API_USERNAME` /
`API_PASSWORD` are configured.

### Optional: Scheduled Retraining

```ini
SCHEDULER_ENABLED=true
RETRAIN_CRON_HOUR=3
RETRAIN_CRON_MINUTE=0
RETRAIN_ESTIMATOR=linear_svc_calibrated
```

The API container then runs an in-process APScheduler that retrains the
classifier daily at the configured UTC time.

### Optional: LLM Assistant

Install Ollama on the host and pull a model:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
```

The API connects to `host.docker.internal:11434` by default.

## API Endpoints

Public:

- `GET /health` - service status

Protected when BasicAuth is enabled:

- `POST /imports/preview` - preview CSV/XLSX headers and auto-detected mapping
- `POST /imports` - upload CSV/XLSX (Pekao, Revolut, auto or generic)
- `GET /imports` / `DELETE /imports/{id}` - import history and cleanup
- `GET /transactions` - list transactions with filters
- `PATCH /transactions/{id}/category` - manual category override
- `POST /transactions/bulk/categorize` - bulk category/type updates
- `POST /transactions/bulk/accept-suggestions` / `reject-suggestions`
- `GET /categories` - system and custom category catalog
- `GET/PATCH /profile` - local user profile
- `GET/POST/PATCH/DELETE /profile/rules` - personal merchant/title rules
- `POST /ml/classify` - predict one transaction category
- `POST /ml/reclassify` - fill ML category suggestions for unlabelled rows
- `POST /ml/retrain` - refit classifier in background
- `GET /forecast?category=&horizon=` - monthly debit forecast
- `GET /anomalies?direction=&contamination=` - flagged transactions
- `GET /subscriptions?min_confidence=` - recurring debits
- `POST /chat` - hybrid LLM assistant
- `GET /stats/*` - overview, cashflow, by-category, net worth, top merchants
- `GET/POST/PATCH/DELETE /assets` - optional investment portfolio

## Web Dashboard

Main UI at <http://localhost:3000>. Built with Next.js 16, React 19,
TypeScript, Tailwind v4, TanStack Query and Recharts.

Pages:

- `/` - KPI cards, cashflow, categories, net worth, merchants, recent rows
- `/transactions` - filters, pagination, category/type edits, ML suggestions
- `/imports` - CSV/XLSX import preview, mapping and history
- `/categories` - system and custom category management
- `/settings` - local profile and personal rules
- `/assets` - optional investment portfolio
- `/forecast` - category/global spending forecast
- `/anomalies` - anomaly review and feedback
- `/subscriptions` - recurring payment detection
- `/ml` - ML quality, retraining and evidence-oriented diagnostics
- `/review` - data quality center for training labels and suggestions
- `/assistant` - local LLM assistant backed by deterministic tools

Auth is handled server-side: `/api/proxy/*` performs HTTP calls to FastAPI and
injects BasicAuth when credentials are configured. Browser code does not see
backend credentials.

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv venv
.venv\Scripts\Activate.ps1
uv pip install -e ".[dev,augment]"
```

Dependency extras are split by role:

- base install: API/runtime demo
- `augment`: Ollama Python client for synthetic training data generation
- `experiments`: heavier research packages
- `dev`: tests, linting, optional local notebooks and developer tools

Run tests:

```powershell
pytest
```

Run API locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload --port 8000
```

Build aggregate ML evidence reports from local/private data:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py --from-db
```

Reports are written to `data/reports/`; private anomaly review files go to
`data/private/`. These paths are gitignored. See `docs/ml-evidence.md`,
`docs/model-card.md` and `docs/demo-runbook.md`.

## Docker

Run all Compose commands from the repository root. Use the same project name
every time so Docker reuses the same images, containers and Postgres volume.

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml up -d --build --force-recreate
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml logs -f api web
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml down
```

Services:

- `postgres` - application database, port 5432
- `api` - FastAPI backend, port 8000
- `web` - Next.js dashboard, port 3000

Ollama runs on the host, not in Compose.

Check that the persistent database volume exists:

```powershell
docker volume ls | findstr postgres-data
```

Expected volume name: `personal-finance-app_postgres-data`.

Avoid these commands during normal work:

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml down -v
docker volume rm personal-finance-app_postgres-data
docker system prune --volumes
```

They remove the Postgres volume and imported/reviewed data. Use `down -v` only
for an intentional clean demo reset.

## Web Dev

```powershell
cd apps/web
npm install
npm run dev
```

Optional `.env.local`:

```ini
API_URL=http://localhost:8000
API_USERNAME=admin
API_PASSWORD=change-me
```

## Project Layout

```text
apps/api/         FastAPI backend
apps/web/         Next.js dashboard
src/finance/      Core package
  ingestion/      Bank CSV/XLSX parsers
  domain/         SQLAlchemy models, enums, DTOs
  db/             Session and migrations
  ml/             Classification, transaction type evidence, forecasting,
                  anomalies and subscriptions
  llm/            Ollama client, Polish router and deterministic tools
tests/            Pytest tests
docker/           Dockerfiles and compose
data/             Runtime/private artifacts, gitignored
notebooks/        Optional local notebooks; `.ipynb` files are ignored by default
scripts/          Evidence, smoke and debug helpers
```

Repository boundaries:

- Production demo path: `apps/web` -> `/api/proxy/*` -> `apps/api` ->
  `src/finance` -> Postgres.
- Research/evidence path: `scripts/`, `src/finance/ml/` and optional local
  notebooks.
- Runtime artifacts: `data/models/`, `data/reports/`, coverage files, caches
  and frontend build files are generated locally and ignored.
- Private data: real bank exports should live in `data/raw/`, `data/private/`
  or outside the repo.

## Architecture

```text
CSV/XLSX exports
      |
      v
src/finance/ingestion
      |
      v
Postgres <---- FastAPI <---- Next.js dashboard
      |            |
      |            +---- chat/router/tools ---- Ollama on host
      |
      +---- ML pipelines
             - category classification: TF-IDF + linear models
             - transaction type classification: evidence-only silver labels
             - forecasting: naive/mean/SES/ARIMA
             - anomaly detection: IsolationForest + robust z-score + rules
             - subscriptions: cadence detector
```

Layers:

- Ingestion parses bank exports into canonical transaction rows.
- Domain models are the shared source of truth for API, ML and tests.
- ML code is library-style and is orchestrated by API endpoints, scripts or
  local notebooks.
- API exposes thin FastAPI routers and middleware.
- Web is the main user-facing interface.

## ML Metrics And Reproducibility

The project keeps separate reports for:

- category classification - supervised 9-class expense category model
- transaction type classification - supervised evidence experiment on silver labels
- forecasting - walk-forward comparison of naive, mean, SES and ARIMA
- anomaly detection - IsolationForest, robust z-score and rule summaries
- subscriptions - recurring payment detector

The aggregate evidence package is produced by:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py --from-db
```

Data policy:

- real bank exports remain local/private,
- public reports contain aggregates and aliases, not raw merchant/title text,
- runtime classifier uses category labels confirmed by the user,
- `transaction_type` evidence currently uses silver labels from import rules.

## Quality Gates

Typical checks:

```powershell
ruff check .
mypy src/finance apps
pytest
cd apps/web
npm run typecheck
```

CI runs linting, tests, frontend checks and dependency audits.
