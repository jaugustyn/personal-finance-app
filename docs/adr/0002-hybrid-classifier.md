# ADR-0002: Hybrid Transaction Classification (LLM + LinearSVC)

- **Status:** ACCEPTED
- **Date:** 2026-05-01
- **Phase:** simplified runtime with diagnostic calibration

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

1. Runtime candidates are Logistic Regression and calibrated LinearSVC with the
   baseline pipeline only. Feature-v2 and other estimators are benchmark-only.
2. Runtime uses the fixed confidence threshold 0.55. Thresholds derived from
   real OOF probabilities remain diagnostics. `other` always requires review.
3. **LLM fallback** uses a configurable local Ollama model and requires both a
   global flag and an explicit request flag. It has no fabricated confidence
   and always requires user acceptance.
4. **LLM-driven augmentation** (`finance.ml.classification.augment`) is a
   separate research experiment and does not enter runtime candidate training.
5. Training is an explicit user action. Candidates are stored in the DB-backed
   registry and activated manually; no scheduler retrains or promotes models.

## Consequences

**Positive:**

- Candidate quality is measured on both primary holdouts, not only stratified
  CV.
- A model may cover only ontology classes with at least 10 confirmed labels;
  unsupported classes remain manual instead of blocking useful training.
- No cloud dependency. Ollama runs locally.

**Negative:**

- Optional LLM fallback still adds a second suggestion path.
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
