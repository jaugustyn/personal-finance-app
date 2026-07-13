# ADR-0002: Classical Category Classifier With Optional Local LLM

- **Status:** accepted
- **Date:** 2026-05-01
- **Updated:** 2026-07-13

## Context

Bank descriptions are short, noisy and repetitive, while the available labels
come from one private user and are strongly imbalanced. The application needs
useful category suggestions without sending financial data to a cloud service
or introducing a model that is difficult to reproduce.

An LLM-only classifier would work without many labels but would be slower,
non-deterministic and difficult to calibrate. A rule-only solution would be
simple but expensive to maintain for changing merchant formats.

## Decision

1. Runtime category candidates are Logistic Regression and calibrated LinearSVC
   on the same TF-IDF baseline.
2. Only manual labels and accepted suggestions with complete confirmation
   provenance may enter training.
3. Time and unseen-merchant holdouts are mandatory. OOF calibration remains
   diagnostic.
4. Runtime uses the fixed threshold `0.55`; `other` always requires review.
5. Candidates are versioned and activated manually after gates, checksum,
   compatibility and smoke checks.
6. Feature-v2 and additional estimators are benchmark-only.
7. Local Ollama fallback is optional, requires double opt-in and always returns
   an unconfirmed suggestion with no fabricated confidence.
8. LLM augmentation remains a separate experiment and does not enter runtime
   candidate training or evaluation.
9. Retraining is an explicit user action; there is no scheduler.

## Consequences

Positive:

- the default experiment is small, understandable and reproducible;
- both candidate models expose probabilities needed by the review policy;
- new-time and new-merchant performance are visible separately;
- no private transaction needs to leave the host;
- an unsupported rare class remains manual instead of blocking all training.

Negative:

- the fixed threshold needs empirical monitoring;
- exact artifact compatibility means dependency upgrades require retraining;
- manual activation and retry add a small operational step;
- an optional LLM fallback still creates a second suggestion path.

## Rejected alternatives

- **LLM-only classification:** too slow and non-deterministic for the main path.
- **Transformer fine-tuning:** disproportionate cost for a small private
  dataset and harder reproducibility.
- **Rules only:** useful for deterministic exceptions, but brittle as the main
  category classifier.
- **Automatic promotion:** unacceptable without review of holdout metrics and
  artifact integrity.

## Acceptance criteria

A runtime candidate needs at least 300 confirmed labels, two supported classes,
both feasible holdouts, macro-F1 at least `0.60` on each and p99 at most
`200 ms` without LLM. Stricter final targets are evidence goals, not claims
made by this ADR.
