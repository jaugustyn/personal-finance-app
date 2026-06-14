# ADR-0003: Anomaly And Subscription Detection With Classical Methods

- **Status:** ACCEPTED
- **Date:** 2026-05-01

## Context

Two core product requirements:

1. **Anomaly detection:** find transactions that significantly deviate from
   category history, for example an appliance purchase inside `food` or a
   transport transaction five times above the usual value.
2. **Subscription detection:** find recurring charges with stable amount and
   cadence (7/30/90/365 days), even when merchant strings vary slightly.

The expected user dataset contains 12-36 months of history, roughly 3-6k
transactions, 9 expense categories and a separate `is_transfer` flag. Each
category usually has 50-800 observations.

## Decision

Use a **hybrid classical method** without autoencoders and without LLM
embeddings:

- **Anomalies:** IsolationForest over simple numeric features (`log_abs`,
  day-of-week/month, merchant frequency, direction) plus robust z-score
  (median + MAD) per `(category, direction)` plus the deterministic
  "new merchant + large amount" rule.
- **Subscriptions:** period detection over dates for a normalized merchant
  name: median interval, +/-10% amount tolerance and at least 2 occurrences by
  default for short histories.

## Consequences

**Positive:**

- Explanations remain readable in the UI, for example "unusually high amount"
  or "new merchant + large amount".
- No GPU and no external ML service.
- Robust z-score is stable for small subpopulations because MAD is less
  sensitive to outliers than a standard z-score.
- IsolationForest can catch multidimensional patterns that z-score alone would
  miss.

**Negative:**

- IsolationForest is less interpretable than pure z-score, so its output is
  combined with rule-based reasons.
- The subscription detector intentionally ignores highly variable charges. In
  this product, variable spending is not treated as a subscription.

## Rejected Alternatives

- **Pure robust z-score.** Very interpretable, but misses cases such as a new
  merchant with an unusual pattern.
- **LOF / embedding-based outlier detection.** More complex, harder to explain
  and unnecessary at this data scale.
- **Merchant autoencoder.** Overkill for the dataset size.
- **Prophet for anomaly detection.** Transaction-level anomaly detection and
  monthly forecasting are separate problems; Prophet is not needed at runtime.

## Success Metrics

- Anomaly precision >= 0.8 on a manually reviewed subset of 50 transactions.
- Subscription recall >= 0.9 on the user's known real subscriptions.
