"""CLI and compatibility facade for category classifier training.

The library implementation lives in smaller modules:

- ``evaluation``: CV, readiness, validation slices and confidence policy inputs.
- ``reports``: thesis/evidence report assembly.
- ``fitting``: final model fitting for persisted artifacts.

This file remains the stable command entry point:

    python -m finance.ml.classification.train --from-db --persist linear_svc
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd

from finance.domain.enums import BankSource
from finance.ingestion import get_parser
from finance.ml.classification.artifacts import build_model_artifact
from finance.ml.classification.constants import (
    CONFIDENCE_THRESHOLDS,
    DEFAULT_FEATURE_SET,
    EVIDENCE_THRESHOLD,
    FEATURE_SETS,
    IDEAL_LABELLED_ROWS,
    MIN_PER_CLASS,
    MINIMUM_LABELLED_ROWS,
    MINIMUM_PER_CATEGORY,
    MODELS_DIR,
    RECOMMENDED_LABELLED_ROWS,
    RECOMMENDED_PER_CATEGORY,
    REPORTS_DIR,
    STRONG_PER_CATEGORY,
    TARGET_THRESHOLD_ACCURACY,
)
from finance.ml.classification.dataset import dtos_to_dataframe, load_training_set
from finance.ml.classification.evaluation import (
    _best_non_dummy,
    _confidence_curve,
    _confidence_point,
    _confusion_hotspots_from_predictions,
    _cross_val_confidence,
    _evaluate_holdout,
    _feature_decision,
    _filter_rare_classes,
    _merchant_group_holdout,
    _model_metrics_from_predictions,
    _per_category_metrics,
    _predict_confidence_after_fit,
    _recommended_thresholds_by_category,
    _time_holdout,
    build_label_readiness,
    build_validation_slices,
    filter_category_training_rows,
)
from finance.ml.classification.evaluation import (
    evaluate as _evaluate,
)
from finance.ml.classification.evaluation import (
    evaluate_feature_v2 as _evaluate_feature_v2,
)
from finance.ml.classification.exceptions import ClassificationError
from finance.ml.classification.external import load_kaggle_personal_finance
from finance.ml.classification.fitting import (
    _feature_builder,
    fit_final,
)
from finance.ml.classification.pipeline import to_features, to_features_v2
from finance.ml.classification.registry import ESTIMATORS
from finance.ml.classification.reports import build_evidence_report

__all__ = [
    "CONFIDENCE_THRESHOLDS",
    "DEFAULT_FEATURE_SET",
    "ESTIMATORS",
    "EVIDENCE_THRESHOLD",
    "FEATURE_SETS",
    "IDEAL_LABELLED_ROWS",
    "MINIMUM_LABELLED_ROWS",
    "MINIMUM_PER_CATEGORY",
    "MIN_PER_CLASS",
    "MODELS_DIR",
    "RECOMMENDED_LABELLED_ROWS",
    "RECOMMENDED_PER_CATEGORY",
    "REPORTS_DIR",
    "STRONG_PER_CATEGORY",
    "TARGET_THRESHOLD_ACCURACY",
    "_best_non_dummy",
    "_confidence_curve",
    "_confidence_point",
    "_confusion_hotspots_from_predictions",
    "_cross_val_confidence",
    "_evaluate_holdout",
    "_feature_builder",
    "_feature_decision",
    "_filter_rare_classes",
    "_guess_source",
    "_load_from_files",
    "_load_synthetic",
    "_merchant_group_holdout",
    "_model_metrics_from_predictions",
    "_per_category_metrics",
    "_predict_confidence_after_fit",
    "_recommended_thresholds_by_category",
    "_time_holdout",
    "build_evidence_report",
    "build_label_readiness",
    "build_validation_slices",
    "evaluate",
    "evaluate_feature_v2",
    "filter_category_training_rows",
    "fit_final",
    "load_training_set",
    "main",
    "to_features",
    "to_features_v2",
]


def _load_from_files(paths: list[Path]) -> pd.DataFrame:
    """Auto-route files to parsers by filename prefix or content sniffing."""
    all_dtos = []
    for path in paths:
        source = _guess_source(path)
        parser = get_parser(source)
        with path.open("rb") as fh:
            all_dtos.extend(parser.parse(fh, filename=path.name))
    return dtos_to_dataframe(all_dtos)


def _guess_source(path: Path) -> BankSource:
    name = path.name.lower()
    if "pekao" in name or "pekaosa" in name:
        return BankSource.PEKAO
    if "revolut" in name or "account-statement" in name:
        return BankSource.REVOLUT
    raise ValueError(f"Cannot infer source for {path}")


def _load_synthetic(path: Path) -> pd.DataFrame:
    """Load a CSV produced by `finance.ml.classification.augment`."""
    df = pd.read_csv(path)
    required = {"text", "abs_amount", "day_of_week", "category"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Synthetic CSV missing columns: {missing}")
    df["source"] = df["source"].fillna("synthetic") if "source" in df.columns else "synthetic"
    return df


def evaluate(*args, **kwargs) -> dict:
    """Compatibility wrapper preserving the historical SystemExit behavior."""
    try:
        return _evaluate(*args, **kwargs)
    except ClassificationError as exc:
        raise SystemExit(str(exc)) from exc


def evaluate_feature_v2(*args, **kwargs) -> dict:
    """Compatibility wrapper for the experimental feature-v2 evaluation."""
    try:
        return _evaluate_feature_v2(*args, **kwargs)
    except ClassificationError as exc:
        raise SystemExit(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-files", nargs="+", type=Path)
    src.add_argument("--from-db", action="store_true")
    p.add_argument(
        "--persist",
        choices=list(ESTIMATORS.keys()),
        default=None,
        help="Refit on the full labelled set with this estimator and save it.",
    )
    p.add_argument(
        "--augment",
        type=Path,
        default=None,
        help="Optional CSV produced by augment.py. Concatenated with real data.",
    )
    p.add_argument(
        "--external-kaggle",
        type=Path,
        default=None,
        help=(
            "Optional Kaggle Personal_Finance_Dataset.csv. Reported as "
            "external_only and real_plus_external experiments."
        ),
    )
    p.add_argument(
        "--feature-set",
        choices=sorted(FEATURE_SETS),
        default=DEFAULT_FEATURE_SET,
        help=(
            "Feature set used only for --persist. Evidence still compares "
            "baseline vs feature_v2."
        ),
    )
    args = p.parse_args(argv)

    if args.from_db:
        from finance.db import SessionLocal

        with SessionLocal() as session:
            df = load_training_set(session)
    else:
        df = _load_from_files(list(args.from_files))

    print(
        f"Loaded {len(df)} rows total; "
        f"{df['category'].notna().sum()} labelled."
    )

    synth = None
    if args.augment is not None:
        synth = _load_synthetic(args.augment)
        print(f"  + augmented with {len(synth)} synthetic rows from {args.augment}")

    external = None
    if args.external_kaggle is not None:
        external = load_kaggle_personal_finance(args.external_kaggle)
        counts = external["category"].value_counts().to_dict()
        print(
            f"  + external Kaggle rows: {len(external)} labelled "
            f"from {args.external_kaggle}; classes={counts}"
        )

    report = build_evidence_report(df, augmented_df=synth, external_df=external)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORTS_DIR / f"classification_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\nSelected experiment: {report['selected_experiment']}")
    for exp_name, exp_report in report["experiments"].items():
        print(f"\nCV macro-F1 per estimator ({exp_name}):")
        for name, info in exp_report["models"].items():
            suffix = " skipped" if info.get("skipped") else ""
            print(
                f"  {name:20s}  macro_f1={info['macro_f1']:.3f}  "
                f"weighted_f1={info['weighted_f1']:.3f}{suffix}"
            )
    decision = report.get("feature_decision", {})
    print(
        "\nFeature-set recommendation: "
        f"{decision.get('recommended_feature_set', 'baseline')} "
        f"({decision.get('reason', 'n/a')})"
    )
    print(f"\nFull report -> {report_path}")

    if args.persist:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model = fit_final(df, args.persist, feature_set=args.feature_set)
        out = MODELS_DIR / f"classifier_{args.persist}_{ts}.joblib"
        artifact = build_model_artifact(
            estimator=args.persist,
            feature_set=args.feature_set,
            pipeline=model,
            report=report,
        )
        joblib.dump(artifact, out)
        latest = MODELS_DIR / "classifier_latest.joblib"
        joblib.dump(artifact, latest)
        print(
            f"Persisted {args.persist}/{args.feature_set} -> {out} "
            f"(and {latest})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
