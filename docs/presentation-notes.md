# Project Presentation Notes

This file is a short guide for presenting the application. It is not meant to
be read word-for-word. Use it as a reminder of what to show, what to say
technically and where ML/AI appears in the project.

## 1. Project Idea

The app is a self-hosted personal finance management system. It combines bank
data import, deterministic rules, ML models and a local language assistant. The
main principle: hard numeric facts are computed by the backend, while the LLM
can only summarize or phrase them in Polish.

Main elements:

- bank transaction import and deduplication,
- transaction type detection, for example purchase, own transfer, salary or
  bank fee,
- expense category classification,
- training-label quality workflow,
- expense forecasting,
- anomaly detection,
- subscription detection,
- local financial assistant based on routing and deterministic tools.

## 2. Dashboard

What it shows:

- KPIs: income, expenses, net balance, monthly average,
- cash flow over time,
- top expenses grouped by merchant,
- most frequent expenses,
- category spending trend,
- month-over-month changes,
- cumulative balance,
- recent transactions.

What to say:

- The dashboard is a summary view, not a model-training surface.
- The data range can be switched between the last 12 months and all data.
- Top expenses are aggregated by normalized merchant name. This reduces noise
  from variants such as `LIDL 1234` and `Lidl sp. z o.o.`.
- The dashboard excludes own transfers by default so they do not distort
  expense analysis.

## 3. Transactions

What it shows:

- the full transaction list,
- direction, amount, merchant, title, category and transaction type,
- ML suggestions with confidence,
- notes and tags,
- bulk operations.

What to say:

- `transaction_type` describes money-flow semantics, for example purchase, own
  transfer, salary or refund.
- `category` describes the budget category of an expense, for example food,
  transport or health.
- Transaction type and category are separate layers. Example: salary has type
  `salary`, but it should not receive an expense category.
- ML suggestions are not automatically treated as truth. The user can accept or
  reject them.
- Accepted and manually assigned categories become training data.

## 4. Data Import

What it shows:

- bank file import,
- column mapping,
- required-field validation,
- import history,
- transaction deduplication.

What to say:

- Bank parsers convert different export formats into one transaction model.
- Deduplication is based on a stable hash from transaction fields, so importing
  the same file twice should not duplicate records.
- Transaction-type rules and personal rules run during import.
- Runtime import still uses deterministic rules for `transaction_type`; the
  transaction-type ML model is evidence-only.

## 5. Categories

What it shows:

- main category list,
- colors used on charts,
- adding custom categories.

What to say:

- Main categories are the target labels for the expense classifier.
- Subcategories can add detail, but the main ML model works on main categories.
- Category colors affect data presentation, not the model.

## 6. Data Quality

What it shows:

- transactions without a category,
- transactions without suggestions,
- low-confidence suggestions,
- rare classes,
- repeated merchants without a rule,
- the "what to do now" panel.

What to say:

- This is the workspace for improving training labels.
- The classifier is only as good as the user-confirmed labels.
- Rare classes are a real multiclass-classification issue: the model has fewer
  examples and can confuse them more easily.
- Before retraining, the goal is to increase the number of confirmed labels,
  especially in weak classes.

## 7. ML Models

What it shows:

- active model status,
- label count,
- classes known by the model,
- Macro-F1,
- training experiment comparison,
- feedback loop,
- most common mistakes,
- `Przetrenuj model` and `Przelicz sugestie` actions.

What to say:

- This is not a manual model switcher.
- The active model changes after retraining and saving a new artifact.
- `Przetrenuj model` builds a new artifact from confirmed labels.
- `Przelicz sugestie` uses the current model to recompute suggestions for
  transactions.
- Macro-F1 matters because class imbalance can hide poor quality on rare
  categories when looking only at weighted metrics.
- The dummy baseline is needed to prove that the model learns more than the
  most frequent class.

## 8. ML: Expense Category Classification

Goal:

- assign an expense transaction to one budget category.

Input data:

- merchant,
- title/description,
- amount,
- transaction direction,
- context features such as transaction type and source.

Approach:

- supervised multiclass classification,
- TF-IDF text features,
- simple numeric and categorical features,
- comparison against baselines,
- reporting Macro-F1, Weighted-F1, per-class metrics and confusion matrix.

How to defend it:

- TF-IDF is a reasonable choice because merchant names and transfer titles are
  short texts with repeated patterns.
- Embeddings are not mandatory when a simpler model provides a measurable and
  explainable baseline.
- The model should not train on its own unconfirmed predictions. Training uses
  manually assigned or user-accepted categories.

## 9. ML: Transaction Type Classification

Goal:

- separate supervised multiclass analysis for `transaction_type`.

Classes:

- `expense`,
- `salary`,
- `income`,
- `refund`,
- `own_transfer`,
- `cash_withdrawal`,
- `debt_payment`,
- `asset_allocation`,
- `other`.

Input data:

- merchant,
- title,
- raw bank category,
- absolute amount,
- direction,
- data source.

Important limitation:

- in v1 the model is a suggestion layer,
- labels come only from confirmed `Transaction.transaction_type` decisions,
- only manual decisions and accepted suggestions are gold labels,
- the model never performs auto-apply during import or reclassification.

How to defend it:

- it satisfies the supervised multiclass ML requirement for transaction type,
- it does not risk breaking production import behavior,
- it allows model-vs-rule comparison and gives metrics for the evidence report.

## 10. Forecast

What it shows:

- expense forecast for the next months,
- category selection or all categories,
- forecast horizon,
- selected model and history length.

What to say:

- Forecasting works on monthly expense time series.
- With short history, the forecast is illustrative.
- The most stable demo is the forecast for all categories because it has more
  data.
- Forecasting individual categories makes sense only when a category has
  regular history.

Models:

- simple time-series baselines,
- mean/naive and SES/ARIMA in the evidence reports.

How to defend it:

- The goal is not a perfect production forecaster, but a correct time-series
  experiment with baselines.
- Personal finance data is short and noisy, so a simple model is often more
  trustworthy than an overcomplicated one.

## 11. Period Summary

What it shows:

- comparison of the current week or month against the previous period,
- income, expenses and net balance,
- biggest category changes,
- top merchants,
- budget limit breaches,
- savings-goal progress.

What to say:

- This is deterministic, not LLM-driven.
- Week means the current calendar week from Monday to today.
- Month means the current month from day 1 to today, compared with the previous
  month.
- If the current month has no data, current values are zero and the delta shows
  the difference against the previous period.

## 12. Anomalies

What it shows:

- transactions requiring review,
- anomaly type,
- priority,
- reasons for flagging,
- feedback: relevant, not relevant, ignore merchant.

ML approach:

- unsupervised component: IsolationForest,
- strengthened with deterministic business rules,
- example rules: very large amount, unusual amount for a merchant, missing
  category or merchant on a large transaction.

What to say:

- IsolationForest helps find unusual points without manual anomaly labels.
- Unsupervised models can produce noise, so the output is combined with rules
  and user feedback.
- Feedback does not delete a transaction. It tells the system whether similar
  cases should have higher or lower priority.

"Unusual pattern (model)" means that the anomaly was mainly indicated by
IsolationForest. The transaction may not violate a simple rule such as "very
large amount" or "missing category", but its feature combination looks unusual
relative to the rest of the data.

## 13. Subscriptions

What it shows:

- recurring payments,
- estimated monthly cost,
- last occurrence,
- confidence.

Approach:

- cadence detection,
- repeated merchant analysis,
- amount-stability check,
- exclusion of own transfers and non-expense transaction types.

What to say:

- This is not a text classifier. It is a temporal-pattern detector.
- Subscriptions are a practical savings-recommendation target because they are
  recurring and easy to review.

## 14. Assets

What it shows:

- investment portfolio,
- positions, quantity, price and PLN value,
- profit/loss,
- value history,
- flow from income to categories to merchants.

What to say:

- This extends the app beyond bank transactions.
- Prices can come from an external source, for example yfinance.
- It does not need to be the main ML part of the demo.

## 15. Assistant

What it shows:

- Polish questions about finances,
- answers backed by backend tools,
- examples: monthly spending, top categories, subscriptions and recommendations.

Key point:

- This is not pure vector RAG for numeric facts.
- The project uses a hybrid approach:
  - intent routing,
  - deterministic tools for data aggregation,
  - a local LLM to phrase the result in natural language.

How to defend it:

- A question like `Na co najwiecej wydalem w styczniu 2026?` requires querying
  structured data, not searching similar documents in a vector database.
- The backend computes hard facts, and the LLM should not invent them.
- This is safer and easier to test than pure RAG for numeric aggregation.

## 16. Settings

What it shows:

- local profile,
- currency,
- payday,
- personal rules.

What to say:

- Personal rules run before ML.
- They can suggest or automatically apply a category or transaction type.
- Example: if the merchant contains a specific name, the transaction can be
  treated as an own transfer or assigned to a category.
- This is a deliberate combination of rules and ML: certain cases are handled
  deterministically, uncertain cases go to the model and review.

## 17. Evidence Package And Reports

What to say:

- The project generates an evidence package for ML/AI evaluation.
- The main combined report is `evidence_package`.
- The report separates:
  - category classification,
  - transaction type classification,
  - forecasting,
  - anomaly detection,
  - subscriptions,
  - privacy check.

Important:

- Public reports must not contain raw merchant names or transfer titles.
- For demos and documentation, cite `summary.md` and aggregate metrics instead
  of private bank exports.

## 18. Main ML Defence Points

Strongest points:

- There are two supervised multiclass tasks:
  - expense category,
  - transaction type as a confirmed-label hybrid suggestion model.
- Forecasting works on monthly time series.
- Unsupervised anomaly detection uses IsolationForest.
- Subscription detection is cadence analysis.
- The local LLM assistant uses deterministic tools for facts.
- The feedback loop lets the user accept, reject and correct labels.
- There are metrics and baselines, not only UI screens.

Limitations worth stating explicitly:

- Model quality depends on the number of confirmed labels.
- `transaction_type` ML is evidence-only, not a production replacement for
  rules.
- Forecasts with short history are illustrative.
- Unsupervised anomalies need feedback because unusual does not always mean
  wrong or suspicious.
- Financial data is private, so public reports should be aggregated and
  anonymized.

## 19. Suggested Demo Order

1. Dashboard: show the `12 months` / `all data` switch.
2. Import: show column mapping and deduplication.
3. Transactions: show transaction type, category, ML suggestion and
   accept/reject.
4. Data Quality: show how training data is improved.
5. ML Models: show model status, Macro-F1, retraining and reclassification.
6. Forecast: show forecast for all categories.
7. Anomalies: show anomaly type and feedback.
8. Subscriptions: show recurring payments.
9. Period Summary: show current-vs-previous period comparison.
10. Assistant: ask a Polish question about specific data.

## 20. Short Lines To Remember

- "Transaction type says what the money flow is; category says which budget
  bucket the expense belongs to."
- "The LLM does not compute facts. The backend computes facts, and the LLM
  explains them."
- "Data Quality is the place for improving training labels."
- "The category model is used in production for suggestions; the transaction
  type model is currently evidence-only."
- "Anomalies combine IsolationForest, business rules and feedback."
- "Forecasting is most useful for all categories and longer histories."
