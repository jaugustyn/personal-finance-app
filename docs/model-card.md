# Model Card — Category Classifier v1

## Model details

| Field | Value |
| --- | --- |
| Name | `category_classifier_v1` |
| Version | Registered model-version UUID |
| Target | One of the 9 system expense categories |
| Candidates | Logistic Regression or calibrated LinearSVC |
| Runtime features | TF-IDF baseline: text, amount and day of week |
| Workflow | `POST /ml/retrain` → candidate report → manual activation |
| Runtime artifact | Immutable candidate path selected by the active DB model version |
| License | MIT for code; private training data is not licensed or published |

The active runtime model must expose calibrated `predict_proba`. Dummy,
uncalibrated LinearSVC and Random Forest remain research benchmarks and cannot
be promoted in iteration 1.

Routine `POST /ml/retrain` evaluates both Logistic Regression and calibrated
LinearSVC with baseline features. The complete ten-variant research experiment is explicit:
`POST /ml/retrain?include_benchmarks=true`. Benchmark mode cannot be combined
with candidate filters.

## Intended use

- Suggest a budget expense category for a single user's transactions.
- Prioritize uncertain transactions for manual review.
- Optionally evaluate a local Ollama fallback as a separate experiment.

The model must not classify transfers, income or other non-expense flows as
budget expenses. It is not suitable for credit decisions, scoring, fraud
accusations or decisions affecting third parties.

## Training labels

Gold labels are limited to transactions with all of the following:

- a category from the fixed 9-class ontology;
- expense-candidate semantics;
- `category_confirmation_method` equal to `manual` or `accepted_suggestion`;
- a non-null confirmation timestamp.

Bank categories, system rules, personal `auto_apply` rules and model/LLM output
are excluded from gold labels until the user confirms the category. Custom
categories remain available in the product but are
excluded from ML v1. No historical labels are automatically backfilled.

Raw bank categories remain stored for future ontology work. Synthetic and
external data are reported separately; they do not enter runtime candidate
training or validation.

## Evaluation and promotion

The source of truth for activation and runtime is the DB model registry. JSON
reports are immutable research/evidence outputs and never select a runtime
model. Reports include macro-F1, weighted-F1, per-class metrics, confusion matrices,
coverage/covered accuracy, log-loss, multiclass Brier score, ECE, reliability
bins and p99 runtime.

Primary validation uses equal-status time and unseen-merchant holdouts.
Stratified 5-fold CV is diagnostic only. Candidate ranking maximizes the worse
of the two holdout macro-F1 values, followed by their mean, covered accuracy and
latency.

Technical promotion requires:

- at least 300 confirmed labels in total;
- at least two classes with 10 confirmed examples each;
- feasible time and merchant holdouts for every class included in the model;
- macro-F1 ≥0.60 on both primary holdouts;
- regression ≤0.02 only relative to an active model evaluated on the same
  frozen evaluation set;
- p99 ≤200 ms for 1000 warmed predictions without LLM.

Thesis-ready additionally requires:

- a manually frozen private test version;
- at least 800 labels and 50 per class;
- 12 represented calendar months and a date span ≥365 days;
- macro-F1 ≥0.75 on both frozen holdouts;
- covered accuracy ≥0.90 with coverage ≥0.50 on both holdouts.

Runtime always uses the global threshold 0.55. OOF calibration, ECE, Brier,
log-loss and candidate global/per-category thresholds are diagnostic only and
cannot modify runtime behavior. `other` always requires review.

## LLM and augmentation

Ollama is restricted to loopback or `host.docker.internal`. Fallback requires a
global flag and `use_llm_fallback=true` for the request. Its category has
`confidence=null`, retains the base `model_confidence` separately and always
requires explicit acceptance.

LLM fallback remains optional and experimental; it is not an alternative active
artifact. A formal comparison can record model tag, digest, hardware, hit rate
and latency percentiles without changing the baseline runtime policy.

## Limitations and privacy

- Evidence comes from one private user and does not establish population-level
  generalization.
- New merchant formats and class imbalance can reduce quality.
- The TF-IDF vocabulary can reveal merchant names; trained artifacts are
  private even though public reports contain aggregates only.
- `transaction_type` is evaluated separately on confirmed user decisions; its
  model is evidence-only and does not participate in runtime suggestions.
- Forecasting, anomalies and subscription evidence remain provisional in this
  iteration.

## Reproducibility

```bash
uv sync --frozen --extra dev
uv run python scripts/build_ml_evidence.py --from-db
uv run python scripts/inspect_report.py --profile classification-strict
```

Python 3.12 and all transitive dependencies are locked in `uv.lock`. Every
artifact records exact Python, scikit-learn, numpy, pandas and joblib versions
and schema version 3.0 is rejected on any mismatch. Deterministic split operations use
`random_state=42`.
