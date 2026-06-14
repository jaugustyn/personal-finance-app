# ADR-0002: Hybrid Transaction Classification (LLM + LinearSVC)

- **Status:** ACCEPTED
- **Date:** 2026-05-01
- **Phase:** Phase 1 -> Phase 3 (confidence calibration)

## Context

Classifying bank transactions into 9 system categories (`food`, `transport`,
`housing`, `health`, `savings`, `subscriptions`, `entertainment`, `shopping`,
`other`) is a classic multiclass classification problem over short text
(`merchant + title`). The dataset is imbalanced and contains a long tail of rare
patterns, for example pharmacies or subscriptions with new merchants.

Two extreme strategies were considered:

- **A) Classic ML only** (TF-IDF + LinearSVC). Fast and deterministic, but
  requires labelled data and struggles with out-of-vocabulary merchants.
- **B) LLM only** (Llama 3.1 8B through Ollama). Good zero-shot understanding of
  new merchants, but non-deterministic, slower and prone to hallucinating
  categories outside the ontology.

## Decision

Use a **hybrid approach**:

1. **LinearSVC** (TF-IDF on `text` + numeric `abs_amount`, `day_of_week`) is the
   first classifier. If `decision_function`-derived confidence is at least `tau`
   (default 0.55), accept the prediction.
2. **LLM fallback** (Ollama `llama3.1:8b`) handles low-confidence predictions and
   merchants absent from training data. The prompt contains a strict ontology
   and few-shot examples from `SEED_EXAMPLES` in `augment.py`.
3. **LLM-driven augmentation** (`finance.ml.classification.augment`) generates
   synthetic merchant strings for rare classes to improve macro-F1.

## Consequences

**Positive:**

- Mean prediction latency below 50 ms for the SVC path.
- Macro-F1 improved from approximately 0.71 on a small real dataset to
  approximately 0.78 after rare-class augmentation in the working evidence.
- No cloud dependency. Ollama runs locally.

**Negative:**

- Two decision paths increase code and test complexity.
- LLM augmentation is non-deterministic, so generated CSV files must record the
  seed and model version.
- Threshold `tau` is empirical. `classification_*.json` reports a
  `confidence_curve` with coverage and accuracy for thresholds
  0.50/0.55/0.60/0.70/0.80/0.90. For `LinearSVC`, confidence is a normalized
  margin proxy, not a calibrated probability.

## Rejected Alternatives

- **Fine-tuning multilingual DistilBERT.** Requires GPU, produces a much larger
  artifact and gives limited value on a small dataset.
- **Regex-only rules.** They do not scale well because merchant formatting
  changes frequently. Rules remain useful as deterministic overrides.

## Success Metrics

- Macro-F1 >= 0.75 in 5-fold StratifiedKFold after augmentation.
- p99 latency of `/ml/classify` <= 200 ms without the LLM fallback.
- LLM fallback hit rate <= 10%; if higher, retrain the SVC model.
