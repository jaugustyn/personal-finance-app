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

- Pekao and Revolut imports, plus a generic CSV/XLSX mapping flow.
- Deduplication, multi-currency conversion and daily exchange rates.
- Transaction list with separate economic type and expense category workflows.
- Dashboard, period summaries, merchant analysis and asset tracking.
- Category suggestions using TF-IDF and linear classifiers.
- Rule-based transaction-type suggestions with explicit user review.
- Forecasting, anomaly and subscription detection.
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
| Runtime        | PostgreSQL, Docker Compose, Python 3.12, `uv`        |

## Quick start

Requirements: Docker Desktop and an optional local Ollama instance.

```powershell
copy .env.example .env
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml up -d --build
```

- Web: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

Stop the stack:

```powershell
docker compose --env-file .env -p personal-finance-app -f docker/docker-compose.yml down
```

`down -v` removes the PostgreSQL volume and should only be used for an
intentional clean start.

Main optional settings:

```ini
AUTH_USERNAME=
AUTH_PASSWORD=
OLLAMA_BASE_URL=http://localhost:11434
LLM_ENABLED=true
LLM_FALLBACK_ENABLED=false
```

Set both auth values to enable BasicAuth. Ollama endpoints other than loopback
or `host.docker.internal` are rejected.

## Local development

Backend:

```powershell
py -3.12 -m pip install uv==0.8.15
uv sync --frozen --extra dev
$env:PYTHONPATH="$PWD\src"
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --port 8000
```

Frontend:

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

Evidence commands and interpretation rules are documented in
[`docs/ml-evidence.md`](docs/ml-evidence.md).

## Privacy

Never publish bank exports, `.env` files, model artifacts or row-level reports.
Keep them in ignored runtime locations such as `data/raw/`, `data/private/`,
`data/models/` and `data/reports/`. The entire `data/` directory and local
environment files are excluded from version control.

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
