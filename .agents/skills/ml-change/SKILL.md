---
name: ml-change
description: Use when changing transaction classification, training/evaluation, feature engineering, confidence diagnostics, LLM augmentation, forecasting, anomaly detection, subscription detection, ML evidence reports, model persistence, or ML API behavior.
---

# ML Change

Preserve explainable baselines and reproducibility. Do not tune only for one private dataset.

Inspect first:

1. Classification: `src/finance/ml/classification/{dataset,pipeline,train,predict,confidence,registry,augment}.py`.
2. Forecasting: `src/finance/ml/forecasting/{pipeline,registry}.py`.
3. Anomalies/subscriptions: `src/finance/ml/anomaly/detector.py`, `src/finance/ml/subscriptions/detector.py`.
4. Evidence: `src/finance/ml/evidence.py`.
5. API and downstream use: `apps/api/routers/ml.py`, `forecast.py`, `anomalies.py`, `subscriptions.py`, `src/finance/llm/`.
6. Tests under `tests/ml/` plus affected API/LLM tests.

Workflow:

1. Identify the ML task affected.
2. Inspect current baseline and metrics.
3. Check for data leakage.
4. Keep the existing baseline comparable.
5. Add or update synthetic/anonymized regression tests.
6. Preserve model artifact compatibility or document migration impact.

For classification changes, report:

- macro-F1,
- weighted-F1,
- confusion matrix impact if available,
- minority class behavior,
- confidence/coverage impact,
- whether TF-IDF + LinearSVC remains comparable.

For forecasting changes, report:

- MAE/MAPE/SMAPE if available,
- horizon,
- validation method.

For anomaly/subscription changes, report:

- precision-oriented behavior,
- examples of expected false positives/false negatives.

Never use private raw data in committed tests or logs. Keep `data/raw/`, `data/private/`, `data/reports/`, and `data/models/` as runtime artifacts.

Validate with:

- `pytest tests/ml`
- Add focused `pytest tests/api` or `pytest tests/llm` when API/tool outputs change.
- `ruff check .` and `mypy src/finance apps` for shared contracts.
