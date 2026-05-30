# Personal Finance Analysis System

Self-hosted system for analyzing and optimizing personal expenses using ML and local LLMs.

## Status

Current focus: Phase 12 — personalization and AI/ML quality improvements.

- Phase 1 ✅ ingestion (Pekao + Revolut), API, UI, Docker, CI
- Phase 2 ✅ ML categorisation (TF-IDF + linear SVC, macro-F1 = 0.82 with LLM augmentation), Nordigen PoC
- Phase 3 ✅ monthly forecasting, IsolationForest anomalies, subscription detector
- Phase 4 ✅ hybrid LLM assistant (heuristic PL router + Ollama tool-calling fallback)
- Phase 5 ✅ HTTP Basic auth, structlog, APScheduler, enriched health, 10-min setup
- Phase 6 ✅ Next.js 16 + shadcn/ui dashboard (KPI, cash flow, net worth, imports, categories, assets, transactions table with inline/bulk edit, forecast/anomalies/subscriptions pages)
- Phase 7 ✅ ML evidence package, code-quality refactors (services, LLM tools, frontend modules), confidence calibration reports
- Phase 8 ✅ ML/AI backend hardening (classifier diagnostics, optional LLM fallback, anomaly/forecast/subscription regressions)
- Phase 9 ✅ category review workflow (transaction-type filters, ML suggestion queue, accept/reject suggestions, deterministic savings recommendations)
- Phase 10 ✅ clean-start validation docs, real-data evidence flow and defence demo runbook
- Phase 11 ✅ backend/AI/ML consistency refactor for stats, transfer filtering and classifier confidence
- Phase 12 ⏳ local profile, personal rules and experimental feature-v2 ML comparison

## From zero to running in 10 minutes

Prerequisites: **Docker Desktop** and (optional) **Ollama** running on the host
for the chat assistant.

```powershell
git clone <repo> finance && cd finance
copy .env.example .env             # Edit .env if you want auth or scheduler
docker compose -f docker/docker-compose.yml up -d --build
```

Then open:

- **Web** (Next.js production dashboard) → <http://localhost:3000>
- API   → <http://localhost:8000/docs>
- UI    (Streamlit lab: asystent + ML/admin) → <http://localhost:8501>
- Health → <http://localhost:8000/health>

Import a CSV from the Next.js `/imports` page (or the Streamlit lab `Home`
page), wait a few seconds for classification, then use the Next.js dashboard
for analytics. Streamlit remains a lab/admin surface for the assistant and ML
developer workflows.

### Optional: enable BasicAuth

Set both in `.env`:

```ini
AUTH_USERNAME=admin
AUTH_PASSWORD=change-me
```

`/health` stays public; all other endpoints require credentials. The Streamlit
UI auto-attaches the same credentials when these env vars are set.

### Optional: enable scheduled retraining

```ini
SCHEDULER_ENABLED=true
RETRAIN_CRON_HOUR=3
RETRAIN_CRON_MINUTE=0
RETRAIN_ESTIMATOR=linear_svc
```

The API container then runs an in-process APScheduler that retrains the
classifier daily at the configured UTC time.

### Optional: enable LLM assistant (Ollama)

Install Ollama on the host (<https://ollama.ai>) and pull a model:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
```

The API connects to `host.docker.internal:11434` by default.

## API endpoints

Public:

- `GET  /health` — service status (db + ollama checks)

Protected (BasicAuth when enabled):

- `POST /imports/preview` — preview CSV/XLSX headers and auto-detected mapping
- `POST /imports` — upload CSV/XLSX (Pekao/Revolut/auto/generic)
- `GET  /imports` / `DELETE /imports/{id}` — import history and cleanup
- `GET  /transactions` — list with filters (`category_state`, `has_suggestion`, `min_confidence`, `transaction_type`)
- `PATCH /transactions/{id}/category` — manual category override (active learning)
- `POST /transactions/bulk/categorize` — bulk category / own-transfer updates
- `POST /transactions/bulk/accept-suggestions` / `reject-suggestions` — promote or dismiss ML category suggestions
- `GET  /categories` — system + user-defined category catalog
- `GET/PATCH /profile` — local user profile: base currency, salary day, savings goal, category limits
- `GET/POST/PATCH/DELETE /profile/rules` — personal merchant/title rules applied before ML suggestions
- `POST /ml/classify` — predict single transaction category with confidence diagnostics and optional LLM fallback
- `POST /ml/reclassify` — bulk-fill `category_predicted` + confidence for unlabelled expense-like rows
- `POST /ml/retrain` — refit classifier in background
- `GET  /forecast?category=&horizon=` — monthly debit forecast (auto-selects best model)
- `GET  /anomalies?direction=&contamination=` — flagged transactions with severity score
- `GET  /subscriptions?min_confidence=` — recurring debits with confidence + cost
- `POST /chat` — hybrid LLM assistant
- `GET  /stats/overview?months=&include_transfers=` — aggregated KPI (income/expenses/net/savings rate)
- `GET  /stats/cashflow?months=&include_transfers=` — monthly cashflow series
- `GET  /stats/by-category?months=&include_predictions=&include_transfers=` — expenses breakdown; confirmed categories by default
- `GET  /stats/networth?months=&include_transfers=` — cumulative balance series
- `GET  /stats/top-merchants?months=&limit=&include_transfers=` — top expense merchants
- `GET/POST/PATCH/DELETE /assets` — optional investment portfolio + yfinance snapshots

## Web dashboard (Next.js)

Production-grade UI at <http://localhost:3000>. Built with Next.js 16 (App Router) +
TypeScript + Tailwind v4 + shadcn/ui-style components + TanStack Query + Recharts.

Pages:

- `/` — KPI cards, cash flow (12m), category donut, cumulative balance, top merchants, recent transactions
- `/transactions` — filterable + paginated table, "to assign" review mode, transaction type badges and ML suggestion accept/reject actions
- `/imports` — CSV/XLSX import preview, generic column mapping, import history
- `/categories` — system/custom category management
- `/settings` — local profile and personal merchant/title rules used before ML
- `/assets` — optional portfolio tracking, yfinance refresh, history and Sankey flow
- `/forecast` — interactive forecast for any category
- `/anomalies` — top flagged transactions sorted by severity
- `/subscriptions` — recurring expense cards with monthly total

Auth is handled server-side: a Next route handler at `/api/proxy/*` forwards
requests to FastAPI and injects `Authorization: Basic` when `API_USERNAME` /
`API_PASSWORD` env vars are set. Browser never sees credentials.

## Streamlit lab (asystent + admin)

Streamlit is intentionally kept as a lab surface, not the production frontend.
It is useful during the defence to show ML/admin workflows and the Polish chat
assistant at <http://localhost:8501>:

- `Home` — imported transactions, predictions, manual reclassify, retrain button
- `📈 Prognoza` — historical monthly spend + N-month forecast
- `🚨 Anomalie` — top flagged rows sorted by severity
- `🔁 Subskrypcje` — detected subscriptions with cost estimate + confidence
- `💬 Asystent` — chat (PL) with deterministic heuristics + optional LLM polishing

## Quick start (dev, without Docker)

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or use `pip` with the same `pyproject.toml`).

```powershell
uv venv
.venv\Scripts\Activate.ps1
uv pip install -e ".[dev,ui,augment]"
```

Dependency extras are split by role: base install is the API/runtime demo,
`ui` adds Streamlit lab dependencies, `augment` adds the Ollama Python client
for synthetic data generation, `poc` adds GoCardless/Nordigen helpers, and
`experiments` keeps heavy research-only packages out of the normal runtime.

Run tests:

```powershell
pytest
```

Build aggregate ML evidence reports from local/private data:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py --from-db
```

See `docs/ml-evidence.md` for the reporting/privacy rules. The script writes
aggregate JSON to `data/reports/` and private anomaly review CSVs to
`data/private/`; both locations are gitignored. Stable aliases
`latest_*.json` and `summary.md` are generated for easy citation. See
`docs/demo-runbook.md` for the clean-start validation and defence demo flow.
See `docs/features/README.md` for the current feature/status/roadmap map.
If local env credentials differ from the app defaults, pass
`--database-url postgresql+psycopg://...`; credentials are masked in errors.

Run API (requires running Postgres — see Docker section):

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload --port 8000
```

> Use the venv's Python directly. The PowerShell `Activate.ps1` may fail on paths with diacritics
> (e.g. `Magisterka Projekt`). Calling `.\.venv\Scripts\python.exe -m uvicorn ...` works regardless.

Run UI:

```powershell
.\.venv\Scripts\python.exe -m streamlit run apps/ui/Home.py
```

## Docker

```powershell
docker compose -f docker/docker-compose.yml up -d
```

Services:

- `postgres` — application database (port 5432)
- `api` — FastAPI backend (port 8000)
- `ui` — Streamlit dashboard (port 8501)
- `web` — Next.js dashboard (port 3000)

Ollama runs on the **host** (not in Compose) to spare CPU/VRAM.

## Web dev (without Docker)

```powershell
cd apps/web
npm install
# optional: set API_URL=http://localhost:8000 in .env.local
npm run dev
```

Open <http://localhost:3000>. Requires the API running (locally or in Docker).

## Project layout

```
apps/api/         FastAPI backend
apps/ui/          Streamlit lab (assistant + ML/admin workflows)
apps/web/         Next.js dashboard (production frontend)
src/finance/      Core package (importable from both apps)
  ingestion/      Bank CSV parsers
  domain/         SQLAlchemy models, enums, DTOs
  db/             Session, migrations
  ml/             Classification, forecasting, anomalies, subscriptions
  llm/            Ollama client, Polish router, tool functions
tests/            Pytest tests
docker/           Dockerfiles + compose
data/             Runtime/private artifacts (gitignored)
notebooks/        EDA + evaluation notebooks (research/lab)
scripts/          Smoke/debug helpers
```

Repository boundaries:

- **Production demo path:** `apps/web` → `/api/proxy/*` → `apps/api` → `src/finance` → Postgres.
- **Lab/research path:** `apps/ui`, `notebooks/`, `scripts/`, `src/finance/ingestion/nordigen.py`.
- **Runtime artifacts:** `data/models/`, `data/reports/`, `coverage.xml`, caches and frontend build files are generated locally and ignored.
- **Private data:** real bank exports should live in `data/raw/`, `data/private/`, or outside the repo. `data/synthetic/` is for generated examples.

## Configuration

Copy `.env.example` to `.env` and adjust values. The API reads config from env vars
via `pydantic-settings`.

Selected variables:

| Var | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://finance:finance@localhost:5432/finance` | Application database |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | empty | Enable HTTP Basic auth on protected endpoints |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed by FastAPI CORS |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-IP rate limit (`0` disables) |
| `SCHEDULER_ENABLED` | `false` | Run APScheduler for daily retraining |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | LLM endpoint for chat polishing |

## Architecture

```
                                 ┌────────────────────┐
   CSV (Pekao/Revolut)  ───►     │  ingestion         │
   GoCardless PoC     ───►     │  (parsers, dedup)  │
                                 └─────────┬──────────┘
                                           ▼
                          ┌──────────────────────────────┐
                          │  Postgres (transactions,     │
                          │  categories, assets, …)      │
                          └─────┬────────────────┬───────┘
                                ▼                ▼
              ┌──────────────────────┐    ┌──────────────────┐
              │  ML pipelines        │    │  FastAPI         │
              │  • TF-IDF + LinSVC   │◄──►│  routers + auth  │
              │  • forecasting       │    │  + rate limit    │
              │  • anomalies         │    │  + CORS          │
              │  • subscriptions     │    └────────┬─────────┘
              │  • LLM router        │             ▼
              └──────────┬───────────┘    ┌──────────────────┐
                         │                │  Next.js (web)   │
                         ▼                │  + Streamlit (ui)│
                  Ollama (host)           └──────────────────┘
```

Layers:

- **Ingestion** — `src/finance/ingestion/` parses bank CSVs into a canonical `Transaction` shape with deterministic dedup hashes.
- **Domain** — `src/finance/domain/models.py` is the single SQLAlchemy 2.0 source of truth used by API, ML and tests. The canonical taxonomy is 8 expense categories plus a separate `transaction_type` layer (`purchase`, own/person transfer, salary, refund, fees, savings/investment) and `is_transfer` for own-account transfers.
- **ML** — `src/finance/ml/` (classification, forecasting, anomaly, subscriptions). Pure libraries — orchestrated from the API, Streamlit lab or notebooks.
- **API** — `apps/api/` exposes thin FastAPI routers, applies BasicAuth/CORS/rate-limit middleware, and proxies the same domain to the web frontend.
- **Frontends** — `apps/web` (Next.js dashboard, production) and `apps/ui` (Streamlit lab/admin/notebook-style assistant).

## ML metrics & reproducibility

Reported on the labelled subset of the synthetic + real CSV corpus
(`data/processed/labelled.parquet`):

| Task | Model | Metric | Value |
| --- | --- | --- | --- |
| Categorisation (8 expense classes + `transaction_type`) | TF-IDF + LinearSVC + LLM augmentation | macro-F1 | **0.82** |
| Categorisation (baseline, no augmentation) | TF-IDF + LinearSVC | macro-F1 | 0.74 |
| Monthly debit forecast (auto-select) | Naive / Mean / SES / ARIMA | MAPE (12m holdout) | 8–14% |
| Anomaly detection | IsolationForest + robust z-score + heuristic rules | precision@20 | ≥ 0.85 (hand-evaluated) |
| Subscription recurrence | rule-based pattern matcher | precision / recall | 0.91 / 0.88 |

Reproduce locally (after seeding the DB and running classification on imports):

```powershell
.\.venv\Scripts\python.exe -m finance.ml.classification.train --estimator linear_svc --report
.\.venv\Scripts\python.exe -m finance.ml.forecasting.evaluate --category groceries --horizon 6
jupyter lab notebooks/01_eda.ipynb        # EDA + confusion matrix
```

Data:

- Real transactions: 2 banks (Pekao XLSX, Revolut CSV), ~3 years, anonymised on import.
- Augmented training set: deterministic synthetic samples generated by `finance.ml.classification.augment` (LLM-assisted, reviewed) — boosts macro-F1 by ~8 pp on minority classes.
- Labelling: bootstrapped from a small hand-labelled seed (~150 rows) and grown via active learning (`PATCH /transactions/{id}/category`).

## Quality gates

CI (`.github/workflows/ci.yml`) runs on every push / PR:

- `ruff check .`
- `mypy src/finance apps` (non-blocking)
- `pytest` (150+ tests, ~75%+ coverage, >=60% coverage gate)
- frontend: `tsc --noEmit` + `eslint src` (apps/web)
