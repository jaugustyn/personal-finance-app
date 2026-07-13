# ADR-0003: Explainable Anomaly and Subscription Detection

- **Status:** accepted architecture, provisional evidence
- **Date:** 2026-05-01
- **Updated:** 2026-07-13

## Context

Personal-finance histories are relatively short, private and rarely contain
reliable anomaly labels. Subscription labels are also incomplete, while users
need understandable reasons for every flagged item.

Heavy representation-learning methods would add dependencies and obscure the
decision path without guaranteeing better results at this scale.

## Decision

Anomalies combine:

- IsolationForest over simple numeric and frequency features;
- robust amount deviation based on median and MAD;
- deterministic rules such as a new merchant with a large amount;
- user feedback and readable reason codes.

Subscriptions use:

- normalized merchant groups;
- median intervals and cadence classes;
- amount-stability checks;
- minimum history requirements and user preferences.

Neither detector uses an LLM or automatically changes transaction data.

## Consequences

Positive:

- results can be explained in the UI;
- no GPU or external model service is needed;
- robust statistics tolerate outliers better than mean-based thresholds;
- rules and model signals complement each other.

Negative:

- IsolationForest can flag valid but unusual purchases;
- variable subscriptions may be missed;
- merchant normalization errors can split or merge recurring groups;
- quality cannot be established without private manual review.

## Rejected alternatives

- **Pure z-score:** transparent but unable to capture multidimensional
  patterns.
- **LOF, embeddings or autoencoders:** additional complexity without justified
  evidence for the expected data scale.
- **LLM classification:** unnecessary for temporal and numeric patterns.
- **Prophet for transaction anomalies:** forecasting and transaction-level
  outlier detection are different tasks.

## Evaluation criteria

Anomalies are evaluated with complete, ordered `precision@20/50` review.
Subscriptions require manual validation of detected and known recurring
payments. Until those reviews are complete, both evidence sections remain
`provisional` and no precision or recall target is claimed as achieved.
