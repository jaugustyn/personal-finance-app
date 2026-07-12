# ML Evidence Package

The purpose of this package is to produce repeatable, aggregate evidence for
the ML/AI parts of the project without committing raw banking data. Raw CSV
files, model artifacts and private anomaly reviews remain local in `data/raw/`,
`data/models/` and `data/private/`.

## What To Generate

```bash
python scripts/build_ml_evidence.py --from-db
```

If the local database uses credentials different from the app configuration:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --database-url postgresql+psycopg://user:password@localhost:5432/finance
```

Optional augmentation:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --augment data/synthetic/augmented.csv
```

Optional public Kaggle dataset as a comparison experiment:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --external-kaggle data/external/kaggle_personal_finance_data/Personal_Finance_Dataset.csv
```

Kaggle data is reported only as `external_only` and
`real_plus_external_training_only`. It
does not replace manually confirmed Polish labels and should not automatically
switch the production model.

The script writes:

- `data/reports/classification_*.json` - real-only and optionally augmented
  category classification reports. They include `dummy_most_frequent`, `logreg`,
  `linear_svc`, `random_forest`, macro-F1, weighted-F1, per-class metrics and
  a confusion matrix. The report also contains the experimental `feature_v2`
  comparison (`merchant_norm`, `transaction_type`, `source`, amount bucket,
  month), `linear_svc_calibrated` as a confidence variant and `label_readiness`.
  The production model remains on the base pipeline until the results are
  reviewed.
- `data/reports/transaction_type_classification_*.json` - a separate
  supervised multiclass experiment for `Transaction.transaction_type` on
  manually confirmed labels. It includes `dummy_most_frequent`, `logreg`,
  `linear_svc`, macro-F1,
  weighted-F1, per-class metrics, a confusion matrix, class counts and classes
  dropped due to low support. The experiment is evidence-only; runtime type
  suggestions use deterministic rules and direction fallback.
- `data/reports/eda_*.json` - safe aggregates for visualization: category
  distributions, monthly cash flow, missing values and top merchants as aliases.
- `data/reports/forecasting_*.json` - walk-forward CV for Naive, Mean3, SES and
  ARIMA per category.
- `data/reports/anomaly_summary_*.json` - public anomaly reason summaries and
  aliased examples.
- `data/reports/subscriptions_*.json` - a public aggregate cadence-detection
  report: detected subscription count, estimated monthly cost, cadence
  distribution and examples as aliases.
- `data/reports/evidence_package_*.json` - the main combined package using
  `schema_version = "3.0"`. Evidence sections are stored under `sections`:
  `category_classification`, `transaction_type_classification`, `forecasting`,
  `anomaly_detection` and `subscriptions`. The package also contains `source`,
  `semantic_note`, `privacy_check`, environment/code manifest, currency
  diagnostics and explicit `section_status` values.
- `data/reports/latest_*.json` and `data/reports/summary.md` - stable files for
  citation.
- `data/private/anomaly_review_*.csv` - private row-level review for top
  anomalies. Do not commit it.

After manually filling the `is_relevant` column (`yes/no`, `1/0`,
`true/false`), recompute anomaly precision:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --review-file data/private/latest_anomaly_review.csv
```

`precision@20` or `precision@50` remains `null` until every row in the
corresponding top-k has been reviewed. `reviewed_at_20/50` exposes completeness;
the denominator is never silently reduced to the labelled subset.

After report generation, run the inspector:

```bash
python scripts/inspect_report.py --profile classification-strict
```

`classification-strict` requires a complete category-classification section
while allowing transaction type, forecasting, anomalies and subscriptions to
remain explicitly `provisional`. `thesis-strict` requires every declared thesis
section to be complete. Both profiles require: `latest_classification.json`,
`latest_transaction_type_classification.json`, `latest_eda.json`,
`latest_forecasting.json`, `latest_anomaly_summary.json`,
`latest_subscriptions.json`, `latest_evidence_package.json`,
`privacy_check_latest.json` and `summary.md`. It also validates the minimal
shape of `latest_evidence_package.json`: schema version, source, five evidence
sections, classification metrics, confusion matrices, anomaly precision fields,
subscription summary and a passed privacy check. Use it as a quick sanity check
before citing results in the thesis or presentation.

## Clean-Start Evidence Flow

1. Start the app on a clean database using `docs/demo-runbook.md`.
2. Import a real bank export through the Next.js `/imports` page.
3. Manually accept/reject suggestions and add seed labels until the classes are
   reasonably balanced.
4. Run retraining and `reclassify`.
5. Generate reports with `build_ml_evidence.py --from-db`.
6. Complete the private anomaly review and rerun the report with `--review-file`.
7. Confirm `inspect_report.py --profile classification-strict`.

## Data Volume Guidelines

The priority is real Polish transactions with a manually confirmed `category`.
`category_predicted` is a suggestion, not ground truth.

- Technical activation: at least 300 confirmed transactions in total. Class
  support is checked only for split/CV feasibility; there is no separate
  20-per-class activation gate.
- Thesis data readiness: at least 800 labels, 50 per class, 12 represented
  calendar months and a span of at least 365 days.

The `label_readiness` report shows which categories are below thresholds and
what should enter the review queue: missing categories, low confidence, rare
classes and repeated merchants with errors.

## Interpretation Criteria

- Technical macro-F1 must be at least 0.60 on both primary holdouts; the
  thesis-ready threshold is 0.75 on both.
- `category_classification` and `transaction_type_classification` must be
  interpreted separately. The first layer classifies the budget expense
  category. The second describes money-flow semantics and is trained only on
  manual decisions and accepted suggestions. Its runtime output still requires
  explicit user confirmation.
- Runtime confidence comes only from Logistic Regression or calibrated
  LinearSVC. Thresholds are derived from real OOF probabilities with minimum
  support and evaluated unchanged on both holdouts.
- Rare-class augmentation is experimental. Report the result even when the
  improvement is small or neutral.
- Forecasting selects the model with the lowest RMSE in walk-forward CV. ARIMA
  is only one candidate, not a requirement.
- Anomaly detection is unsupervised, so final quality should be described with
  a manual local `precision@20` / `precision@50` review from the private CSV.
- Subscriptions are reported as cadence detection, not supervised
  classification. Validate quality by manually reviewing examples.

## Privacy

Use only aggregates, merchant aliases and anonymized examples in documentation
and presentations. Do not show full transfer titles, merchant names or model
artifacts with a real TF-IDF vocabulary. The script masks credentials from
`--database-url` in error messages.
