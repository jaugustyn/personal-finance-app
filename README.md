# Personal Finance App

Self-hosted application for importing and analysing personal-finance data. It
combines a FastAPI backend, a Next.js dashboard, classical ML and an optional
local Ollama assistant. Financial calculations are performed by deterministic
domain services; the LLM is not a source of numeric facts.

## Project status

The project is actively developed. Import, transaction management, analytics,
the dashboard and the category-model lifecycle are operational. Real bank
exports, trained models and reports generated from private data are not
included in the repository.

On a clean database, the absence of an active category model is expected.
Training becomes available after collecting enough explicitly confirmed labels;
activation is always manual. Forecasting, anomaly detection, subscription
detection and transaction-type ML are implemented but remain provisional from
the validation perspective.

## Main capabilities

- Transactional accounts shared by imports and manual entries, including one
  multi-currency account for Revolut.
- Pekao and Revolut imports, plus a generic CSV/TSV/TXT mapping flow.
- Account-scoped deduplication, conversion of foreign amounts to PLN and daily
  exchange rates.
- Imported and manually entered transactions with separate economic type and
  expense category workflows.
- Dashboard, period summaries and merchant analysis.
- Category suggestions using TF-IDF and linear classifiers.
- Rule-based transaction-type suggestions with explicit user review.
- Forecasting, anomaly and subscription detection.
- Manual fixed-charge schedules with transaction matching and explicit payment
  entry.
- Approximate gross asset tracking for accounts, investments, deposits, loans
  receivable, retirement wrappers, crypto and physical assets, with manual
  history, a compact analysis view and optional fixed-rate projections.
- Polish local assistant backed by deterministic finance tools.

## Architecture

```text
Next.js web -> /api/proxy/* -> FastAPI -> src/finance -> PostgreSQL
                                      -> Ollama (optional, local only)
```

| Layer          | Technology                                           |
| -------------- | ---------------------------------------------------- |
| API and domain | FastAPI, Pydantic, SQLAlchemy, Alembic               |
| Web            | Next.js, React, TypeScript, Tailwind, TanStack Query |
| Data and ML    | pandas, scikit-learn, statsmodels, joblib            |
| Runtime        | PostgreSQL, Docker Compose, Python 3.14, `uv`        |

## Quick start

Requirements: Docker Desktop and an optional local Ollama instance.

```powershell
copy .env.example .env
# Set a unique, URL-safe POSTGRES_PASSWORD in .env before the first start.
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml up -d --build
```

- Web: <http://localhost:3000>

The default Compose stack exposes only the web application and binds it to
`127.0.0.1`. PostgreSQL and FastAPI remain available only inside the Compose
networks. `docker compose ... ps` reports the internal API readiness state.

Stop the stack:

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml down
```

`down -v` removes the PostgreSQL volume and should only be used for an
intentional clean start.

Changing `POSTGRES_PASSWORD` in `.env` does not rotate the password stored in
an existing PostgreSQL volume. Rotate it inside PostgreSQL first or use an
intentional clean start; never delete a volume that contains the only copy of
the data.

Main optional settings:

```ini
AUTH_USERNAME=
AUTH_PASSWORD=
APP_LOCK_COOKIE_SECURE=false
API_TRUSTED_HOSTS=localhost,127.0.0.1,api
WEB_TRUSTED_HOSTS=localhost,127.0.0.1,[::1]
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
LLM_ENABLED=true
LLM_FALLBACK_ENABLED=false
```

Set both auth values to enable BasicAuth at the web entry point and at FastAPI.
Ollama endpoints other than loopback or `host.docker.internal` are rejected. An
optional inactivity lock can be enabled from Settings; set
`APP_LOCK_COOKIE_SECURE=true` only when the browser reaches the application over
HTTPS.

The currently supported deployment is local-only. Do not publish the web, API
or database ports directly to the internet.

`LLM_ENABLED` is the server-wide kill switch. When it is enabled, Ollama usage
for the Assistant can also be turned on or off at runtime in Settings. The
Assistant model can be selected there from models already installed in the
local Ollama instance; `OLLAMA_MODEL` remains the default. Deterministic
questions and financial calculations remain available when the selected model
is disabled, missing or unavailable. Category fallback continues to use its
separate, default-off configuration.

The trusted-host lists reject requests with an unexpected `Host` header. Their
defaults cover local development, tests and communication between the web and
API containers; do not replace them with a wildcard. The containers run with a
read-only root filesystem. Only `/tmp`, the Next.js runtime cache and the
application `data/` mount remain writable where required.

The example URL reaches Ollama on the host from the API container. When the API
itself is started outside Docker, use `OLLAMA_BASE_URL=http://localhost:11434`.

If the local lock code is lost, disable it from the host:

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml exec api python scripts/reset_app_lock.py
```

## Local development

Start only PostgreSQL with the explicit loopback-only development override:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d postgres
```

Backend:

```powershell
winget install --id astral-sh.uv --exact
uv python install 3.14
uv sync --python 3.14 --frozen --extra dev
$env:PYTHONPATH="$PWD\src"
uv run alembic upgrade head
$env:API_DOCS_ENABLED="true"
uv run uvicorn apps.api.main:app --reload --port 8000 --no-access-log
```

API documentation is disabled by default and is available at
<http://localhost:8000/docs> only after explicitly enabling it for local
development.

After installing `uv` for the first time, reopen PowerShell if the command is
not yet visible. `uv sync` creates the project-local `.venv` automatically;
manual activation is not required because project commands use `uv run`.

Frontend (Node.js 24):

```powershell
cd apps/web
npm ci
npm run dev
```

Quality checks:

```powershell
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
cd apps/web
npm run typecheck
npm run lint
npm run build
```

## ML workflow

The application deliberately separates:

- `transaction_type`: economic meaning of the flow, such as expense, salary,
  refund or own transfer;
- `category`: one of nine system budget categories for qualifying expenses.

Only manual categories and accepted suggestions with confirmation provenance
are gold labels. Category training requires at least 300 such labels. Classes
with at least 10 examples may enter a model; at least two supported classes and
feasible time and unseen-merchant holdouts are required.

A default retraining job compares Logistic Regression and calibrated LinearSVC
on the same baseline features. Candidates are versioned, evaluated and manually
activated or rolled back. Runtime uses a fixed confidence threshold of `0.55`;
OOF calibration remains diagnostic. Feature-v2 and additional estimators are
research-only benchmarks. There is no automatic retraining scheduler.

Transaction-type ML is a separate evidence-only experiment. Runtime type
decisions use deterministic suggestions, user rules and a safe debit/credit
fallback.

PLN is the single analytical currency. A foreign transaction contributes to
totals and models only when it has a positive rate and a valid PLN conversion;
otherwise it remains visible in its original currency and is reported as
omitted from calculations.

Evidence commands and interpretation rules are documented in
[`docs/ml-evidence.md`](docs/ml-evidence.md).

## Privacy

Never publish bank exports, local `.env` files, model artifacts or row-level
reports. Runtime content under `data/` and local environment files matching
`.env*` are excluded from version control. `.env.example` is the only tracked
environment template.

The optional inactivity lock protects an application left open in a browser.
It does not encrypt the database, exports or runtime files and does not replace
the operating-system lock, HTTPS or BasicAuth for an exposed deployment.
Use full-disk encryption and treat downloaded CSV files and model artifacts as
private data. The default Docker configuration is intentionally local-only.

## Documentation

| Document                                                                                | Purpose                                             |
| --------------------------------------------------------------------------------------- | --------------------------------------------------- |
| [`project-overview.md`](docs/project-overview.md)                                       | Scope, architecture and current status              |
| [`current-methodologies-and-solutions.md`](docs/current-methodologies-and-solutions.md) | Technical methodology and implementation choices    |
| [`model-card.md`](docs/model-card.md)                                                   | Category-classifier use, evaluation and limitations |
| [`ml-evidence.md`](docs/ml-evidence.md)                                                 | Reproducible evidence workflow                      |
| [`validation-runbook.md`](docs/validation-runbook.md)                                   | Clean-start and validation workflow                 |
| [`docs/adr/`](docs/adr/)                                                                | Accepted architecture decisions                     |

Code is available under the MIT License. Private data and locally trained
artifacts are not part of the license grant.
