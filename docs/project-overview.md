# Project Overview

This document summarises the project's scope, architecture and current state.
Detailed ML criteria live in the [model card](model-card.md), while
implementation details are described in
[current methodologies](current-methodologies-and-solutions.md).

## Goal and scope

The project is a single-user, self-hosted system for personal-finance analysis.
It covers the complete path from bank-file ingestion through data review and
analytics to classical ML experiments and a local natural-language assistant.

The project evaluates whether relatively simple, explainable methods are
sufficient for private financial data with limited labels and short time
series. The main evaluation questions are:

1. Can TF-IDF with a linear classifier provide useful expense-category
   suggestions on real, user-confirmed labels?
2. How well does the model generalize to later transactions and unseen
   merchants?
3. Can classical anomaly, forecasting and cadence methods provide useful,
   reviewable signals without heavy infrastructure?
4. Can a local LLM improve usability while deterministic tools remain the
   source of financial facts?

No empirical conclusion is claimed until it is supported by locally generated
evidence.

## System architecture

```text
Browser
  -> Next.js dashboard and /api/proxy/*
  -> FastAPI routers
  -> finance domain services
  -> PostgreSQL

Optional local path:
  FastAPI -> Ollama for routing, summaries or category fallback
```

Main boundaries:

- `apps/api`: HTTP layer, middleware, authentication and schemas;
- `apps/web`: Polish operational dashboard;
- `src/finance`: reusable domain, ingestion, analytics, ML and LLM logic;
- `alembic`: database migrations;
- `scripts`: evidence and maintenance commands;
- `tests`: API, domain, ingestion, ML and LLM tests;
- `data`: private runtime files, ignored by Git.

FastAPI routers are intentionally thin. Domain logic belongs in `src/finance`,
parsing in `src/finance/ingestion`, and ML in `src/finance/ml`.

## Data flow

1. A Pekao, Revolut or generic file is parsed into a common transaction DTO.
2. The import service normalizes fields, obtains the date-specific PLN exchange
   rate when available, calculates a deduplication hash and stores the original
   bank values.
3. Transaction-type rules and category sources create provisional suggestions.
4. The user reviews or corrects the economic type and expense category.
5. Only explicit manual decisions and accepted suggestions become ML labels.
6. Deterministic analytics feed the dashboard and LLM tools.

User-maintained fixed charges form a separate planning schedule. They do not
create bank transactions or change realised financial totals. A transaction
can be linked manually to a scheduled occurrence; the reversible link records
payment status without changing the transaction itself.

PLN is the fixed analytical currency. Foreign records without a complete,
positive-rate PLN conversion remain available for review and export but are
excluded from amounts, analytics and model datasets.

Two concepts remain separate throughout the system:

- `transaction_type` describes the economic flow, for example `expense`,
  `salary`, `refund` or `own_transfer`;
- `category` describes the budget bucket of an eligible expense.

This prevents income, transfers and other non-expense flows from entering the
expense-category model.

## ML and AI components

| Component | Current approach | Status |
| --- | --- | --- |
| Expense category | TF-IDF, amount and weekday; Logistic Regression or calibrated LinearSVC | Operational candidate lifecycle |
| Transaction type | Deterministic suggestions; supervised comparison on confirmed labels | Evidence-only ML |
| Forecasting | Complete-month series; baseline, damped trend and seasonal candidates with horizon-matched walk-forward evaluation | Provisional |
| Anomalies | IsolationForest, robust statistics and explainable rules | Provisional |
| Subscriptions | Merchant normalization, cadence and amount stability | Provisional |
| Fixed charges | Manual PLN schedule with calendar-based future dates | Operational |
| Assistant | Polish routing and deterministic tools with optional local Ollama phrasing | Operational, optional LLM |

The category model is the primary ML workflow. It uses versioned candidates,
mandatory time and unseen-merchant holdouts, manual activation, checksums and
runtime compatibility checks. A clean installation contains no active model by
design.

The other analytical modules are useful application features, but their final
validation still depends on private-data review and evidence generation.

## Safety and privacy

- Real exports and row-level reports are never committed.
- Model artifacts are private because a TF-IDF vocabulary may reveal merchant
  names.
- Ollama is restricted to a local host and LLM fallback requires double opt-in.
- Numeric answers from the assistant use SQL-backed or deterministic tools.
- Optional BasicAuth, CORS, rate limiting, security headers and import
  validation protect the single-host deployment.
- An optional server-enforced inactivity lock hides the browser UI after a
  configurable idle period. Its scrypt-protected code and process-local session
  are intentionally separate from accounts or multi-user authentication.

The project is not designed for multi-user banking, credit decisions, fraud
accusations or regulated financial advice.

## Reproducibility and quality

- Python is fixed to 3.12 and dependencies are locked in `uv.lock`.
- Model artifacts record exact Python and core ML-library versions.
- Dataset fingerprints, validation memberships and aggregated metrics are
  stored with candidate reports.
- The frontend uses TypeScript, ESLint and a production build check.
- The backend uses pytest with coverage, Ruff and Mypy.
- Docker Compose provides the local PostgreSQL, API and web stack.

The evidence package records the code revision and dirty flag, runtime versions,
data/model identifiers, privacy diagnostics and explicit section statuses.

## Current status

| Area | State |
| --- | --- |
| Import, transactions, currencies and analytics | Operational |
| Dashboard and review workflows | Operational |
| Category training, activation and rollback | Operational; requires local labels |
| Transaction-type rules and review | Operational |
| Category model results | Not bundled; generated from private data |
| Forecasting, anomalies, subscriptions and type ML | Implemented, validation provisional |
| Manual fixed-charge schedules | Operational |
| Frozen private evaluation set | Backend available, hidden from normal UI |
| Final evidence package | Pending sufficient confirmed data |

Private datasets, trained models and final metric packages are generated
locally and are not distributed with the repository.

## Deliberate trade-offs

- Single-user hosting instead of accounts, roles and multi-tenancy.
- Classical models instead of transformer fine-tuning for a small private
  dataset.
- Local process jobs instead of a distributed task queue.
- Manual model activation instead of automatic deployment.
- Lightweight structured logs instead of a full observability stack.
- Rules for deterministic cases and ML only where uncertainty is useful.

## Key references

- [Category classifier model card](model-card.md)
- [ML evidence workflow](ml-evidence.md)
- [Clean-start validation runbook](validation-runbook.md)
- [Category-classification ADR](adr/0002-hybrid-classifier.md)
- [Anomaly and subscription ADR](adr/0003-anomaly-subscription-detection.md)
