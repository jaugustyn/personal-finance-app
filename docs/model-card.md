# Model Card — Expense Category Classifier v1

## Summary

| Field | Value |
| --- | --- |
| Target | A supported subset of nine system expense categories |
| Candidates | Logistic Regression and calibrated LinearSVC |
| Features | Transaction text, absolute amount and day of week |
| Output | Category suggestion, confidence and top predictions |
| Activation | Versioned candidate, technical gates and manual promotion |
| Runtime policy | Fixed threshold `0.55`; `other` always reviewed |

No trained artifact or result from private data is distributed with the
repository. A clean installation therefore reports no active model.

## Intended use

The model supports a single user by:

- suggesting an expense category;
- prioritising uncertain transactions for review;
- providing aggregate evidence for model evaluation.

It does not classify income, transfers or other non-expense flows. It must not
be used for credit scoring, fraud accusations, decisions affecting third
parties or regulated financial advice.

## Labels and scope

The ontology contains `food`, `transport`, `subscriptions`, `health`,
`entertainment`, `housing`, `savings`, `shopping` and `other`. A particular
artifact may cover only the classes that have sufficient support.

A training row must have:

- one of the system categories;
- expense semantics and debit direction;
- `category_confirmation_method` equal to `manual` or
  `accepted_suggestion`;
- a non-null confirmation timestamp.

Bank mappings, system rules, personal `auto_apply` rules, model/LLM suggestions
and custom categories are excluded. Existing records are not automatically
backfilled as gold labels. Synthetic and external data remain separate
experiments and never enter runtime candidate training or evaluation.

## Model and features

The baseline combines:

- word TF-IDF n-grams 1-2 over `merchant + title`;
- `char_wb` TF-IDF n-grams 3-5;
- `log1p(abs_amount)` with scaling;
- one-hot encoded day of week.

Routine retraining evaluates exactly Logistic Regression and calibrated
LinearSVC. Dummy, uncalibrated LinearSVC, Random Forest and feature-v2 are
benchmark-only and cannot be activated.

## Evaluation

Two primary holdouts have equal importance:

- a time holdout representing later transactions;
- a grouped holdout representing unseen merchants.

The time boundary includes complete booking dates. The shared training pool
contains only rows before that boundary and excludes every merchant group
present in the merchant holdout, including newly confirmed transactions added
after a freeze. Both slices may overlap with each other, but neither overlaps
the training pool.

Frozen sets store separate fingerprints of both slices, including features
and confirmation provenance. Missing or changed evaluation data invalidates
the set before training or the explicit LLM experiment. Transaction/import
deletion invalidates membership atomically with deletion. Notes and changes
outside the evaluation slices do not invalidate a set. Older frozen sets
without slice fingerprints must be explicitly frozen again; no snapshot is
reconstructed from potentially changed data.

OOF predictions from stratified CV provide calibration diagnostics only.
Candidate ranking uses the lower holdout macro-F1 first, followed by mean
macro-F1, covered accuracy and latency.

Because these holdouts guide model selection, they are validation sets. A
final thesis evaluation needs a separate untouched test set after model and
feature choices have been fixed.

Reports include macro-F1, weighted-F1, per-class metrics, confusion matrices,
coverage, covered accuracy, log-loss, multiclass Brier score, ECE, reliability
bins and p99 latency.

Technical promotion requires:

- at least 300 confirmed labels in total;
- at least two classes with 10 examples each;
- feasible time and merchant holdouts for all included classes;
- macro-F1 at least `0.60` on both holdouts;
- p99 no greater than `200 ms` for 1000 warmed predictions without LLM;
- regression no greater than `0.02` only against an active model evaluated on
  the same frozen evaluation set.

The fixed runtime threshold `0.55` is an application policy, not a claim of
90% accuracy. OOF-derived thresholds are reported but do not control runtime.

The optional strict-evaluation status additionally uses a manually frozen private
validation set, broader class support and stricter metrics. It is deliberately separate
from everyday activation and hidden from the normal UI.

## Artifact lifecycle

`POST /ml/retrain` creates candidates but never activates them. Each artifact
stores its pipeline, classes, feature schema, confidence policy, metrics,
dataset fingerprint, evaluation-set reference, environment versions and
SHA-256 checksum.

Activation verifies technical gates, checksum, Python and exact core ML-library
versions, then performs a smoke prediction. Previous compatible versions remain
available for rollback. Runtime loads only the artifact referenced by the
active database record.

## Optional LLM path

Category fallback may call only a local Ollama endpoint and requires both the
global switch and `use_llm_fallback=true`. An LLM result:

- remains a suggestion;
- has `confidence=null`;
- retains the original `model_confidence`;
- requires explicit user acceptance.

LLM augmentation is also a separate research experiment and is not part of the
runtime training set.

## Limitations

- Evidence from one user does not establish population-level generalisation.
- Rare classes and new merchant formats can produce unstable results.
- Merchant vocabulary inside a TF-IDF artifact is private information.
- The fixed confidence threshold requires empirical monitoring.
- Transaction-type ML, forecasting, anomalies and subscriptions are outside
  this model card and currently have provisional evidence status.

## Reproduction

```bash
uv sync --frozen --extra dev
uv run python scripts/build_ml_evidence.py --from-db
uv run python scripts/inspect_report.py --profile classification-strict
```

The supported runtime is Python 3.14. Split operations use `random_state=42`,
and artifact schema `3.0` rejects incompatible environments.
