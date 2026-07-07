# Application Features, Status And Roadmap

Status date: **2026-06-05**. This document is the product map for the project:
what already exists, what state each module is in and what should be planned
next. The main `README.md` remains the quick-start and architecture entry point.

## Scope

The project is a self-hosted personal finance analysis system:

- production demo path: **Next.js dashboard -> FastAPI -> PostgreSQL**,
- research/evidence path: **scripts + ML modules + local notebooks without
  private outputs**,
- AI/ML path: **classification, forecasting, anomalies, subscriptions and a
  local LLM assistant**,
- privacy model: real bank exports, model artifacts and private reports stay
  local.

The current focus is quality hardening and ML/AI evidence. The system is
functional, but ML quality still depends mostly on clean imports, manual
category review and fresh evidence reports built on local real data.

## Status Legend

| Status | Meaning |
| --- | --- |
| Done | Implemented and working in the normal application flow. |
| In progress | Exists partially or needs validation on real data. |
| Planned | A sensible next step, but not required for the current demo. |
| Deferred | Deliberately outside the current thesis/demo scope. |

## Feature Map

| Area | Feature | Status | Notes |
| --- | --- | --- | --- |
| Data import | Pekao SA import | Done | CSV/XLSX parser and bank-category mapping where the bank label is useful. |
| Data import | Revolut import | Done | PLN/USD statements and generic column mapping. |
| Data import | Generic CSV/XLSX import | Done | Header preview, manual column mapping and fallback parser. |
| Data import | Deduplication | Done | Deterministic import hashes reduce duplicates on repeated imports. |
| Data import | `transaction_type` rules | Done | Detects purchase, own transfer, person transfer, salary, income, refund, cash withdrawal, bank fee and savings/investment. |
| Data import | Personal rules before ML | In progress | Merchant/title rules can suggest or automatically set category, type and transfer flags. Needs tuning after real imports. |
| Transactions | Transaction table | Done | Filtering, pagination, inline category editing and bulk categorization. |
| Transactions | Assignment mode | Done | Prioritizes missing category, missing suggestion and low confidence. |
| Transactions | Accept/reject ML suggestions | Done | Accepting a suggestion turns it into a manual label; rejection removes a bad suggestion from the queue. |
| Categories | 9 main expense categories | Done | `food`, `transport`, `subscriptions`, `health`, `entertainment`, `housing`, `savings`, `shopping`, `other`. |
| Categories | `transaction_type` separated from category | Done | Transfers, salaries, income, refunds, cash withdrawals, fees and investments do not pollute expense categories. |
| Categories | Custom category catalog | Done | Available in API/UI, while the thesis ML taxonomy remains based on the 9 system categories. |
| Profile | Local user profile | Done | Base currency, payday, monthly savings goal and category limits. |
| Profile | Merchant/title rules | Done | CRUD in settings and API. Default mode is suggestion; trusted rules can use `auto_apply`. |
| Dashboard | Main KPI dashboard | Done | Income, expenses, net cash flow, savings rate and recent transactions. |
| Dashboard | Cash flow, category, net worth and merchant charts | Done | Transfer semantics and confirmed-category semantics are consistent with backend statistics. |
| Import UI | Upload and preview | Done | Next.js page for preview, mapping and import history. |
| Assets | Optional investment portfolio | Done | Side feature using yfinance, snapshots and portfolio views. Not the core ML part. |
| Stats API | Overview/cashflow/by-category/net worth/top merchants | Done | Defaults to confirmed categories; predictions only via explicit diagnostic parameter. |
| Security | BasicAuth | Done | Optional auth through env; health endpoints stay public. |
| Security | CSV import/export hardening | Done | File limits, MIME/extension checks and formula-injection protection. |
| Observability | Logs and health checks | Done | structlog, request ID, `/health`, `/health/live`, `/health/ready`. |
| Observability | Prometheus/Grafana | Deferred | Removed from current scope as excessive for a single-user self-hosted demo. |

## AI/ML Components

| Component | Role | Status | Quality Notes |
| --- | --- | --- | --- |
| Transaction category classification | Suggests one of 9 expense categories. | In progress | Baseline TF-IDF + LinearSVC, compared with Logistic Regression/RF/Dummy, calibrated LinearSVC option and feature-v2 experiment. Quality depends on confirmed labels. |
| `transaction_type` classification | Reports a multiclass transaction-type experiment. | Done | Evidence-only silver-label model using `Transaction.transaction_type`; compares Dummy/LogReg/LinearSVC and does not replace runtime rules. |
| Confidence diagnostics | Returns category, confidence, source, model category, threshold and fallback information. | Done | Runtime and evidence use the same confidence interpretation. |
| Optional LLM fallback | Uses local Ollama only for low-confidence single classification when enabled. | Done | Not used in bulk reclassification to avoid slow and unstable calls. |
| ML suggestion queue | Fills `category_predicted` for uncategorized expense-like transactions. | Done | A suggestion is not ground truth until accepted by the user. |
| Feature-v2 classification | Adds `merchant_norm`, `transaction_type`, `source`, amount bucket and month. | In progress | Evidence-only experiment until it clearly beats the baseline on macro-F1 and threshold accuracy. |
| LLM augmentation | Generates synthetic transaction descriptions for rare classes. | In progress | Must be reported separately as `real_only` vs `augmented`; it does not replace real labels. |
| Forecasting | Forecasts monthly expenses per category or globally. | Done | Naive, Mean3, SES and ARIMA with walk-forward CV. Requires enough monthly history. |
| Anomaly detection | Flags unusual expenses. | Done | Hybrid IsolationForest + robust z-score + rules. Needs private precision@20/50 review on fresh data. |
| Subscription detection | Detects recurring charges. | Done | Interpretable cadence detector based on merchant normalization, amount stability and cyclicity. |
| LLM assistant | Polish assistant for questions and recommendations. | Done | Heuristic routing and deterministic tools first; the LLM only describes results and must not invent numbers. |
| ML evidence package | Builds classification, transaction type, EDA, forecasting, anomaly, subscriptions and combined evidence reports. | In progress | Report code is ready; fresh `latest_*` files still depend on clean import and manual review. |

## Current Gaps

- The largest evidence gap is a fresh clean-start report set:
  `latest_classification.json`, `latest_transaction_type_classification.json`,
  `latest_eda.json`, `latest_forecasting.json`,
  `latest_anomaly_summary.json`, `latest_subscriptions.json`,
  `latest_evidence_package.json` and `summary.md` after a new real import and
  manual category review.
- `transaction_type` evidence is a silver-label experiment. It satisfies the
  supervised multiclass analysis requirement, but it is not an independent
  production model yet.
- Classification quality depends on label count and balance. Do not train on
  `category_predicted`; ground truth is only accepted or manually set
  `category`.
- Feature-v2 exists, but should remain experimental until it beats the baseline
  on clean-start real data.
- Anomalies require private review: label the top 20/50 flags and publish only
  aggregate precision, without raw transactions.
- Subscriptions will benefit from user feedback: confirmed, ignored and stable
  merchants.
- The LLM assistant should grow through deterministic tools, not by asking the
  model to calculate facts from a prompt. RAG should be described as a hybrid:
  function calling / heuristic routing plus a local LLM for explanation.

## Planned Work

### Phase 13 - Data Quality And External Dataset Experiments

- Add a local workflow for external datasets in `scripts`: Kaggle-like CSV data
  -> normalized transactions -> mapping to 9 categories.
- Compare `real_only`, `external_only`, `mixed` and `mixed + calibration`.
- Document the mapping from external categories to the local 9-class taxonomy.
- Keep raw external files in `data/external/` or outside the repository.
- Decide whether feature-v2 should become the default runtime model.

Implementation status:

- Kaggle `ramyapintchy/personal-finance-data` is supported by
  `scripts/prepare_external_classification_data.py`.
- The dataset is mapped to the local classification schema and can be reported
  as `external_only` and `real_plus_external`.

Example local commands:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_external_classification_data.py
.\.venv\Scripts\python.exe -m finance.ml.classification.train --from-db --external-kaggle data\external\kaggle_personal_finance_data\Personal_Finance_Dataset.csv
```

### Phase 14 - Active Learning And Review UX

- Add review counters: missing category, missing suggestion, low confidence,
  high confidence and rejected suggestions.
- Add a "remember this merchant" action directly in transaction review.
- Prioritize review by ML value: rare classes, low confidence and frequent
  repeated merchants.
- Add diagnostics explaining why a transaction is or is not a category
  suggestion candidate.

### Phase 15 - Better Personalization

- Extend personal rules with ignored merchants for subscriptions and anomalies.
- Add feedback for subscriptions: confirmed/ignored.
- Use category limits and savings goal more strongly in deterministic
  recommendations.
- Add conflict diagnostics when several personal rules match one transaction.

### Phase 16 - Final Defence Package

- Generate fresh evidence reports on a clean local database.
- Update `docs/model-card.md`, `docs/ml-evidence.md` and
  `docs/project-overview.md` with current metrics.
- Prepare a stable demo flow: import -> category suggestions -> review ->
  retrain/reclassify -> dashboard -> forecast -> anomalies -> subscriptions ->
  assistant.
- Keep raw CSV files, private reviews and model artifacts out of Git.

## Inspiration From Professional Apps

Research date: **2026-05-29**. These points are not requirements for the current
demo; they are backlog ideas from the personal-finance app market.

### What Commercial And Open-Source Apps Do Well

| App | Notable Features | Useful Ideas For This Project |
| --- | --- | --- |
| [YNAB](https://www.ynab.com/features/) | Bank import, multi-device work, offline sync, family sharing, category templates and custom views. | Simpler cashflow-based budgeting and category templates. |
| [Monarch Money](https://help.monarch.com/hc/en-us/articles/360048883631-Creating-Your-Budget-in-Monarch) | Monthly cashflow budget: income = expenses + savings, goals, reports and household collaboration. | Better connection between budget, savings goal and recommendations. |
| [Monarch AI](https://help.monarch.com/hc/en-us/articles/16116906962452-About-Monarch-s-AI-Features) | AI Assistant, AI Insights and Weekly Recap with optional household context. | Weekly/monthly deterministic summaries, with LLM used only for wording. |
| [Copilot Money](https://help.copilot.money/en/articles/3971267-transaction-types) | Strong transaction-type split: Income, Internal Transfer, Regular; corrections can create rules. | Confirms the project direction: transaction type should stay separate from expense category. |
| [Copilot Recurrings](https://help.copilot.money/en/articles/3760068-creating-recurrings) | Manual and semi-automatic recurring schedules, including non-monthly cadence. | Editing, pausing and archiving detected subscriptions and bills. |
| [Rocket Money](https://help.rocketmoney.com/en/articles/2677184-premium-membership-features) | Custom budgets, tags, notes, transaction splitting, automation rules, subscription cancellation, goals and net worth. | Tags, notes, split transactions and automation rules are valuable; cancellation/bill negotiation is out of scope. |
| [PocketGuard](https://pocketguard.com/) | Simple spendable-money view after subtracting bills, goals and necessary expenses. | "Available to spend" based on forecast, limits and recurring payments. |
| [PocketSmith](https://www.pocketsmith.com/features/) | Cash projections, what-if scenarios and budget calendar. | What-if scenarios and future-payment calendar fit the current forecasting direction. |
| [Tiller](https://help.tiller.com/en/articles/3279649-what-is-tiller-and-how-does-it-work) | Spreadsheet-first workflow, full data control, automatic feeds and flexible templates. | CSV/XLSX export and spreadsheet-oriented analysis views for advanced users. |
| [Lunch Money](https://lunchmoney.app/features) | Bank/CSV/API imports, tags, rules engine, recurring expenses, calendar, multi-currency, analytics. | Rules engine, tags, calendar and multi-currency are closest to the project scope. |
| [Actual Budget](https://actualbudget.org/) | Local-first privacy, envelope budgeting, sync, optional E2EE and custom reports. | Strengthen the privacy-first/self-hosted narrative and add configurable reports. |

### Highest-Return Ideas For This App

1. **Review Center**
   A dedicated data-quality panel: uncategorized transactions, low confidence,
   missing suggestions, rejected suggestions, repeated merchants without rules
   and rare classes. This directly improves training data and ML quality.

2. **Available To Spend**
   A view showing how much can still be spent by month end after recurring
   payments, savings goals, expected bills and category limits. This connects
   profile settings, subscriptions, forecasting and statistics.

3. **Payment Calendar**
   Calendar of detected subscriptions, bills, salary and predicted large
   expenses. It should allow marking items as confirmed, ignored, paused,
   yearly or quarterly.

4. **What-If Scenarios**
   Simple scenarios such as "what if food spending drops by 10%", "what if
   Netflix is cancelled", "what if the savings goal increases by 300 PLN".
   Calculations should be deterministic; the LLM only explains the result.

5. **Tags, Notes And Split Transactions**
   Categories are not flexible enough for every analysis. Tags and notes add a
   second descriptive axis without expanding ML classes. Split transactions are
   useful for mixed purchases.

6. **Automation Rules With Diagnostics**
   Extend personal rules with historical testing, conflict detection, priority,
   preview of "what this rule would change" and explicit `suggest_only` vs
   `auto_apply`.

7. **Weekly/Monthly Recap**
   Automatic recap of biggest category changes, top merchants, breached limits,
   new subscriptions, anomalies and savings-goal progress. All data should be
   computed by tool functions.

8. **Saved Views And Analytical Export**
   Saved transaction filters and CSV/XLSX export for spreadsheets. This is
   simpler than a full BI module but useful in the same way as Tiller/Lunch
   Money workflows.

9. **Personal Context For AI**
   Optional context: household, fixed costs, non-negotiable costs, savings
   preferences and priorities. This is deterministic recommendation context,
   not demographic data for a model.

10. **Configurable Reports**
    Reports such as cashflow, budget vs actual, category trends, merchant
    trends, transfer audit, subscriptions, anomaly review and savings-goal
    progress. Useful for both the user and the thesis defence.

### Deliberately Lower-Priority Features

- Automatic subscription cancellation and bill negotiation: interesting as a
  product, but requires external service integrations and is outside the
  self-hosted/privacy-first scope.
- Credit score and credit report: heavily US-market-specific and not useful for
  this thesis.
- Full family collaboration / multi-user mode: valuable for SaaS, but conflicts
  with the current single-user self-hosted assumption.
- Automatic savings transfers: requires permission to execute financial
  operations and adds unnecessary risk.
- Mobile widgets and a native app: good polish, but lower return than data
  quality, ML evidence and a stable dashboard.

## Target Data For Better AI/ML Quality

For useful clean-start evaluation:

- classification minimum: **300-500 confirmed labels**,
- classification target: **800-1500 confirmed labels**,
- common categories: **100+ examples** each,
- rare categories: **40-60 minimum**, **80-120 preferred**,
- `transaction_type` rules: **20-50 examples** for own transfer, person
  transfer, salary, refund, cash withdrawal, bank fee and investments,
- forecasting: **6 months minimum**, **12-24 months preferred**,
- anomaly/subscription review: at least **top 20/50 manually reviewed
  anomalies** and several months of repeated transactions.

Mixed PL/EN data is acceptable. The model should see realistic bank strings in
their original language instead of artificially translated descriptions.

## Out Of Current Scope

- Multi-user SaaS, OAuth, billing and tenant isolation.
- Fine-tuned transformer classifier without comparison against a TF-IDF baseline.
- LLM as the source of truth for financial sums.
- Automatic online bank integration.
- Prometheus/Grafana stack.
- Committing real bank exports, private anomaly reviews or local model artifacts.
