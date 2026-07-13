# Personal Finance ML - Project Overview

> A compact briefing for someone seeing the project for the first time. It
> covers the goal, architecture, key decisions, ML/AI components and current
> status.

## 1. Project Goal

**A self-hosted system for personal expense analysis and optimization using
classical ML and a local LLM.**

Master's thesis project, WSEI Krakow, 2026, Applied Computer Science. Scope:
end-to-end application from bank CSV ingestion, through ML classification,
anomaly detection, forecasting and subscription detection, to a production web
dashboard and a natural-language assistant.

### Research Hypotheses

1. A hybrid classifier (TF-IDF + LinearSVC with an LLM fallback for low
   confidence) can reach macro-F1 >= 0.75 on a real dataset of about 2k labelled
   transactions while keeping p99 latency below 200 ms without the LLM fallback.
2. LLM augmentation for rare classes improves F1 for underrepresented
   categories such as `health`, `housing` and `savings`.
3. Hybrid anomaly detection (IsolationForest over numeric features + robust
   median/MAD z-score per category + rules) can produce useful precision@20
   while keeping explanations readable in the UI.
4. Classical forecasting methods (Naive / Mean / SES / ARIMA) over monthly
   category series are sufficient for short personal-finance histories without
   adding heavier dependencies such as Prophet.

## 2. Technology Stack

| Layer | Technology |
| --- | --- |
| Backend API | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic |
| Database | PostgreSQL in runtime, SQLite in selected tests |
| ML | scikit-learn, statsmodels, pandas |
| LLM | Ollama with a local instruct model |
| Web frontend | Next.js App Router + React + TypeScript + Tailwind + TanStack Query + Recharts |
| Observability | structlog JSON logs + `X-Request-ID` + health/readiness endpoints |
| Auth | HTTP Basic for single-user self-hosting |
| Containers | Docker Compose: api, web, postgres |
| CI | GitHub Actions for lint, tests, frontend checks and audits |

## 3. High-Level Architecture

```text
Next.js web app
  -> /api/proxy/* route handlers with optional BasicAuth
  -> FastAPI API
  -> src/finance domain package
  -> PostgreSQL

Optional:
  FastAPI -> Ollama on the host for LLM fallback and assistant responses.
```

Main directories:

```text
apps/api/         FastAPI backend: routers, middleware and security
apps/web/         Next.js dashboard
src/finance/      Importable domain package used by API, scripts and tests
  ingestion/        CSV/XLSX parsers: Pekao, Revolut, generic
  domain/           SQLAlchemy models, Pydantic DTOs, enums
  ml/
    classification/   category classifier, training, prediction, augmentation
    transaction_type/  evidence-only experiments on confirmed labels
    anomaly/          IsolationForest + robust z-score + rules
    forecasting/      Naive, Mean, SES, ARIMA + walk-forward CV
    subscriptions/    cadence detector
  llm/              Ollama client, Polish router, tool calls
alembic/          database migrations
docs/             ADRs, model card, evidence docs and demo notes
tests/            backend, ML and domain tests
data/             private/runtime artifacts, ignored by Git
scripts/          evidence and maintenance helpers
```

Repository boundaries:

- **Production demo path:** `apps/web` -> `/api/proxy/*` -> `apps/api` ->
  `src/finance` -> PostgreSQL.
- **Research/evidence path:** `scripts/`, `src/finance/ml/` and optional local
  notebooks without private outputs.
- **Runtime artifacts:** `data/models/`, `data/reports/`, cache files and
  frontend builds are local and ignored.
- **Private data:** real bank exports belong in `data/raw/`, `data/private/` or
  outside the repository.

## 4. Architecture Decisions

| ADR | Decision | File |
| --- | --- | --- |
| 0002 | Hybrid classifier: TF-IDF + LinearSVC first, local LLM fallback for low confidence, LLM augmentation for rare classes. | [`docs/adr/0002-hybrid-classifier.md`](adr/0002-hybrid-classifier.md) |
| 0003 | Hybrid anomaly detection: IsolationForest + robust z-score + rules, and subscriptions via cadence detection. | [`docs/adr/0003-anomaly-subscription-detection.md`](adr/0003-anomaly-subscription-detection.md) |
| 0004 | Lightweight observability: structlog + health checks, no Prometheus/OpenTelemetry by default. | [`docs/adr/0004-observability.md`](adr/0004-observability.md) |

## 5. ML And AI Components

### 5.1 Expense Category Classification

**Input:** merchant + title + absolute amount + day of week.

**Output:** one of 9 expense categories (`food`, `transport`, `housing`,
`health`, `savings`, `subscriptions`, `entertainment`, `shopping`, `other`) with
confidence. Money-flow semantics are handled separately by `transaction_type`,
so salaries, refunds and transfers do not pollute the expense ontology.

- **Pipeline:** `ColumnTransformer` with TF-IDF char/word features over text and
  `StandardScaler` over numeric features, followed by Logistic Regression or a
  calibrated LinearSVC.
- **Training:** explicit `POST /ml/retrain`; the default job compares both
  baseline candidates and stores immutable registry versions.
- **LLM augmentation:** `augment.py` generates synthetic merchant strings for
  rare classes using Ollama.
- **Evaluation:** mandatory time and unseen-merchant holdouts; OOF predictions
  provide calibration diagnostics.
- **Runtime prediction:** only the active DB-registered artifact is loaded. A
  fixed threshold of 0.55 controls review; low-confidence cases may optionally
  use the local LLM fallback.

Indicative results are documented in `docs/model-card.md`.

### 5.2 Transaction Type Classification

The second supervised experiment covers multiclass `transaction_type` analysis.
Target classes are `expense`, `salary`, `income`, `refund`, `own_transfer`,
`cash_withdrawal`, `debt_payment`, `asset_allocation` and `other`.

Labels come only from manual decisions and accepted suggestions. Bank and
system rules remain a suggestion layer, while the calibrated model can only
create review suggestions. The ordinary debit/credit fallback is silent; only
more specific results enter review. Inputs are transaction text plus `raw_transaction_type`,
`abs_amount`, `direction` and `source`. The report compares the rule baseline,
`DummyClassifier`, `LogisticRegression` and calibrated `LinearSVC`.

Interpretation is intentionally separated:

- `transaction_type` describes money-flow semantics.
- `category` describes the budget category of an expense.

### 5.3 Anomaly Detection

The detector combines IsolationForest over simple numeric features (`log_abs`,
day-of-week/month, merchant frequency, direction), robust z-score per
`(category, direction)` and deterministic rules such as "new merchant + large
amount". The UI shows severity and human-readable reasons, so the result remains
interpretable despite the unsupervised model.

### 5.4 Forecasting

Forecasting uses monthly category time series and walk-forward CV. Candidate
models are Naive (last value), rolling Mean, SES and ARIMA. The best model is
selected by RMSE and returns a `ForecastResult` with MAPE/RMSE and an
N-month forecast.

### 5.5 Subscription Detection

For each normalized merchant name, the detector analyzes transaction dates,
median interval and amount stability. It returns cadence
(`weekly`, `biweekly`, `monthly`, `yearly`), confidence and estimated monthly
cost.

### 5.6 Local LLM Assistant

The assistant is a hybrid system, not pure vector RAG for numeric facts. A
Polish heuristic router detects intents such as spending, top merchants,
subscriptions, forecasting, anomalies and savings recommendations. It calls
deterministic domain tools first. Ollama may then summarize or rephrase the
computed result in Polish.

Financial facts are computed by backend functions. The LLM should not invent
amounts, dates or categories.

## 6. Security And Observability

Security:

- Optional HTTP Basic auth through `AUTH_USERNAME` / `AUTH_PASSWORD`.
- Security headers: CSP, `X-Frame-Options: DENY`, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy`.
- CSV import limits: 10 MiB, extension/MIME allowlist and empty-file
  validation.
- CSV export escapes formula injection cells (CWE-1236).
- Sliding-window in-memory rate limit per IP.
- Configurable CORS through `CORS_ALLOW_ORIGINS`.
- Dependency audits in CI are non-blocking.

Observability:

- JSON logs to stdout through `structlog`.
- Request correlation through `X-Request-ID`.
- Health endpoints: `/health`, `/health/live`, `/health/ready`.
- No Prometheus/Grafana by default to keep the self-hosted demo small.

## 7. Tests And Quality

- Backend tests cover parsers, API routers, security checks, ML helpers and
  evidence builders.
- Property-based tests cover selected CSV preview/import behavior.
- Frontend quality checks use TypeScript and ESLint.
- Backend linting uses Ruff; mypy can be run for type checking.
- CI runs lint, tests, builds and dependency audits.

## 8. Project Status

| Area | Status |
| --- | --- |
| Bank ingestion, API, basic UI, Docker, CI | Done |
| Category classification, LLM augmentation | Done |
| Forecasting, anomalies, subscriptions | Done |
| Local LLM assistant with deterministic tools | Done |
| BasicAuth, structured logs and health checks | Done |
| Next.js dashboard | Done |
| ML evidence package and report inspector | Done |
| Category review workflow and deterministic recommendations | Done |
| Clean-start validation and final demo evidence | In progress / local-data dependent |

## 9. Conscious Trade-Offs

- **Single-user self-hosting:** no multi-tenancy, OAuth or email notifications.
- **PostgreSQL runtime:** SQLite is only used where tests support it.
- **No distributed tracing:** request-id correlation is enough for one node.
- **Local LLM only:** better privacy and no API cost, but slower responses.
- **No transformer fine-tuning:** the labelled dataset is small; TF-IDF + SVC is
  easier to explain and cheaper to run.
- **No automatic user-defined merchant-to-category rules yet:** category
  management exists, but automatic merchant rules are outside the current scope.

## 10. Real Input Data

- Pekao SA: roughly two years of main-account history.
- Revolut: multi-currency accounts, roughly one year of history.
- Combined local dataset: about 3,800 transactions and about 2,200 manually
  labelled examples for training.
- Class imbalance: `food` dominates; `savings` and `health` are rare. Transfers,
  salaries and refunds are represented by `transaction_type`, not by expense
  categories.

## 11. Most Thesis-Relevant Parts

1. Hybrid category classification with LLM fallback and model card.
2. Walk-forward CV for forecasting.
3. Hybrid anomaly detection with IsolationForest, robust z-score and rules.
4. LLM augmentation for rare classes and its macro-F1 impact.
5. Practical DevOps: Docker Compose, CI, audits, health checks and logs.
6. Tests and evidence reports that make the ML claims reproducible.

## 12. Useful Files To Open

1. `README.md` - quick start and scope.
2. `docs/project-overview.md` - this overview.
3. `docs/adr/0002-hybrid-classifier.md` - key ML decision.
4. `docs/model-card.md` - model limitations, metrics and reproducibility.
5. `src/finance/ml/classification/pipeline.py` - TF-IDF + numeric pipeline.
6. `src/finance/ml/classification/train.py` - training and evaluation.
7. `apps/api/main.py` - middleware stack.
8. `apps/web/src/app/page.tsx` - dashboard entry point.

## 13. URLs

| Component | URL |
| --- | --- |
| Web app | <http://localhost:3000> |
| API + Swagger | <http://localhost:8000/docs> |
| Health | <http://localhost:8000/health> |
| PostgreSQL | localhost:5432, database `finance` |
| Ollama host | localhost:11434 |

## 14. Runtime Footprint

- Approximately 2 GB RAM for the app stack without a loaded LLM model.
- Ollama memory depends on the selected local model.
- Cold start is roughly several seconds after PostgreSQL is ready.
- SVC prediction latency is typically below 50 ms; LLM fallback is much slower
  and depends on local hardware.
