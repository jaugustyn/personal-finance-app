# ML Evidence Workflow

The evidence package turns private local data into reproducible aggregate
reports. Raw transactions, merchant names, model artifacts and row-level review
files must remain outside the repository.

## Prerequisites

For complete category evidence, the database needs:

- at least 300 confirmed expense categories;
- at least two classes with 10 examples each;
- feasible time and unseen-merchant holdouts;
- a trained candidate that passed the gates and was manually activated.

Without an active model, report generation may still describe data readiness,
but `classification-strict` correctly fails. This is expected on a clean
database.

## Generate reports

```bash
uv run python scripts/build_ml_evidence.py --from-db
uv run python scripts/inspect_report.py --profile classification-strict
```

Use an explicit local database URL only when it differs from application
configuration:

```bash
uv run python scripts/build_ml_evidence.py \
  --from-db \
  --database-url postgresql+psycopg://user:password@localhost:5432/finance
```

Credentials are masked in database errors.

Optional synthetic augmentation and a public comparison dataset are recorded
as separate experiments:

```bash
uv run python scripts/build_ml_evidence.py \
  --from-db \
  --augment data/synthetic/augmented.csv \
  --external-kaggle data/external/kaggle_personal_finance_data/Personal_Finance_Dataset.csv
```

They are never mixed into runtime candidate fitting or validation. Bank files
loaded with `--from-files` do not contain confirmation provenance and therefore
cannot silently become gold labels.

## Outputs

| Location | Content |
| --- | --- |
| `data/reports/latest_classification.json` | Active category-model metrics and label readiness |
| `data/reports/latest_transaction_type_classification.json` | Evidence-only type experiment or skipped diagnostics |
| `data/reports/latest_eda.json` | Aggregate data profile with merchant aliases |
| `data/reports/latest_forecasting.json` | Walk-forward forecasting results |
| `data/reports/latest_anomaly_summary.json` | Aggregate anomaly reasons and review metrics |
| `data/reports/latest_subscriptions.json` | Cadence and estimated-cost summary |
| `data/reports/latest_evidence_package.json` | Combined schema `3.0` package and section statuses |
| `data/reports/summary.md` | Short human-readable summary |
| `data/private/latest_anomaly_review.csv` | Private row-level anomaly review |

Timestamped versions are also written for audit. Stable `latest_*` files are
convenient inputs for the inspector and later analysis.

## Anomaly review

Fill `is_relevant` in the private review file with `yes/no`, `1/0` or
`true/false`, then regenerate:

```bash
uv run python scripts/build_ml_evidence.py \
  --from-db \
  --review-file data/private/latest_anomaly_review.csv
```

`precision@20` and `precision@50` remain `null` until every item in the
corresponding ordered top-k has been reviewed. The denominator is never reduced
to only labelled rows. If fewer than 50 rows were produced, precision@50 is not
claimed.

## Validation profile

- `classification-strict` requires complete category-classification evidence
  and a passing privacy check. Transaction type, forecasting, anomalies and
  subscriptions may remain explicitly `provisional`.

The profile validates required files, schema shape, key metrics, confusion
matrices and the public privacy check. A structural pass does not by itself
prove model quality; metric interpretation remains a separate analysis step.

## Interpretation

- Category and transaction-type classification are separate tasks.
- Category runtime compares Logistic Regression and calibrated LinearSVC on
  baseline features. The fixed threshold is `0.55`; OOF thresholds are
  diagnostics.
- A class with 10 examples is merely eligible for training, not sufficiently
  validated for a final conclusion.
- Forecasting selects among simple candidates by walk-forward RMSE; short
  histories remain uncertain.
- Anomaly detection is unsupervised and must be evaluated with manual top-k
  review.
- Subscription output is cadence detection and requires manual validation.

## Privacy rules

- Do not commit anything from `data/raw`, `data/private`, `data/models` or
  `data/reports` when it was generated from real data.
- Public evidence may contain only aggregates, aliases and fingerprints.
- Do not publish TF-IDF model artifacts; their vocabulary can reveal merchants.
- The local `data/` directory and every `.env` file remain outside version
  control.

The generator checks public payloads against raw merchant/title values and
aborts when it detects a possible leak.
