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

1. Runtime candidates are Logistic Regression or calibrated LinearSVC with the
   baseline or feature-v2 pipeline. Margin proxies cannot be promoted.
2. Thresholds are derived from real OOF probabilities and evaluated unchanged
   on time and unseen-merchant holdouts. `other` always requires review.
3. **LLM fallback** uses a configurable local Ollama model and requires both a
   global flag and an explicit request flag. It has no fabricated confidence
   and always requires user acceptance.
4. **LLM-driven augmentation** (`finance.ml.classification.augment`) generates
   synthetic merchant strings for rare classes to improve macro-F1.

## Consequences

**Positive:**

- Candidate quality is measured on both primary holdouts, not only stratified
  CV.
- No cloud dependency. Ollama runs locally.

**Negative:**

- Two decision paths increase code and test complexity.
- LLM augmentation is non-deterministic, so generated CSV files must record the
  seed and model version.
- Candidates are never activated automatically. Manual promotion and rollback
  operate on versioned, checksummed artifacts with exact dependency checks.

## Rejected Alternatives

- **Fine-tuning multilingual DistilBERT.** Requires GPU, produces a much larger
  artifact and gives limited value on a small dataset.
- **Regex-only rules.** They do not scale well because merchant formatting
  changes frequently. Rules remain useful as deterministic overrides.

## Success Metrics

- Macro-F1 >= 0.75 on both frozen thesis holdouts.
- p99 latency of `/ml/classify` <= 200 ms without the LLM fallback.
- LLM fallback hit rate <= 10%; if higher, retrain the SVC model.
