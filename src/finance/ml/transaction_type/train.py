"""Evaluate an evidence-only multiclass classifier for transaction_type."""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.svm import LinearSVC

from finance.domain.enums import TransactionType
from finance.ml.transaction_type.dataset import LABEL_SOURCE, prepare_training_frame
from finance.ml.transaction_type.pipeline import build_pipeline, to_features

MIN_PER_CLASS = 2
DEFAULT_N_SPLITS = 5
REPORTS_DIR = Path("data/reports")

ESTIMATORS: dict[str, Callable[[], BaseEstimator]] = {
    "dummy_most_frequent": lambda: DummyClassifier(strategy="most_frequent"),
    "logreg": lambda: LogisticRegression(
        max_iter=2000, class_weight="balanced", C=1.0, n_jobs=None
    ),
    "linear_svc": lambda: LinearSVC(C=1.0, class_weight="balanced"),
}


def _filter_rare_classes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    counts = df["transaction_type"].value_counts().to_dict()
    keep = {label for label, count in counts.items() if count >= MIN_PER_CLASS}
    dropped = {label: int(count) for label, count in counts.items() if count < MIN_PER_CLASS}
    return df[df["transaction_type"].isin(keep)].reset_index(drop=True), dropped


def _per_class_metrics(report: dict, labels: list[str]) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for label in labels:
        metrics = report.get(label, {}) if isinstance(report, dict) else {}
        out[label] = {
            "precision": float(metrics.get("precision", 0.0) or 0.0),
            "recall": float(metrics.get("recall", 0.0) or 0.0),
            "f1": float(metrics.get("f1-score", 0.0) or 0.0),
            "support": int(metrics.get("support", 0) or 0),
        }
    return out


def evaluate(
    df: pd.DataFrame,
    *,
    n_splits: int = DEFAULT_N_SPLITS,
    seed: int = 42,
) -> dict[str, object]:
    labelled = prepare_training_frame(df)
    if labelled.empty:
        return {
            "skipped": True,
            "reason": "No valid transaction_type silver labels.",
            "label_source": LABEL_SOURCE,
            "models": {},
            "class_counts": {},
            "dropped_rare_classes": {},
        }

    labelled, dropped = _filter_rare_classes(labelled)
    if labelled.empty or labelled["transaction_type"].nunique() < 2:
        return {
            "skipped": True,
            "reason": "Not enough transaction_type classes after rare-class filtering.",
            "label_source": LABEL_SOURCE,
            "n_total_labelled": int(len(labelled)),
            "n_classes": int(labelled["transaction_type"].nunique()) if not labelled.empty else 0,
            "models": {},
            "class_counts": {},
            "dropped_rare_classes": dropped,
        }

    X = to_features(labelled)  # noqa: N806
    y = labelled["transaction_type"].astype(str)
    labels = sorted(y.unique())
    n_splits = min(n_splits, int(y.value_counts().min()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    models: dict[str, dict[str, object]] = {}
    for name, factory in ESTIMATORS.items():
        pipe = build_pipeline(factory())
        try:
            y_pred = cross_val_predict(pipe, X, y, cv=cv, n_jobs=None)
            raw_report = classification_report(
                y,
                y_pred,
                labels=labels,
                output_dict=True,
                zero_division=0,
            )
            models[name] = {
                "macro_f1": float(f1_score(y, y_pred, average="macro", zero_division=0)),
                "weighted_f1": float(
                    f1_score(y, y_pred, average="weighted", zero_division=0)
                ),
                "report": raw_report,
                "per_class": _per_class_metrics(raw_report, labels),
                "confusion_matrix": confusion_matrix(y, y_pred, labels=labels).tolist(),
                "labels": labels,
                "skipped": False,
            }
        except Exception as exc:  # noqa: BLE001
            models[name] = {
                "macro_f1": 0.0,
                "weighted_f1": 0.0,
                "report": {},
                "per_class": {},
                "confusion_matrix": [],
                "labels": labels,
                "skipped": True,
                "error": str(exc),
            }

    return {
        "skipped": False,
        "label_source": LABEL_SOURCE,
        "label_source_note": (
            "Silver labels come from Transaction.transaction_type. They may be "
            "system-rule labels, personal-rule labels or manual corrections; "
            "this evidence experiment does not replace runtime rules."
        ),
        "target": "transaction_type",
        "feature_columns": ["text", "abs_amount", "direction", "source"],
        "n_total_labelled": int(len(labelled)),
        "n_classes": int(y.nunique()),
        "labels": labels,
        "known_transaction_types": [item.value for item in TransactionType],
        "class_counts": {str(k): int(v) for k, v in y.value_counts().to_dict().items()},
        "dropped_rare_classes": dropped,
        "n_splits": int(n_splits),
        "models": models,
    }


def build_evidence_report(
    df: pd.DataFrame,
    *,
    n_splits: int = DEFAULT_N_SPLITS,
    seed: int = 42,
) -> dict[str, object]:
    report = evaluate(df, n_splits=n_splits, seed=seed)
    report.update(
        {
            "report_type": "transaction_type_classification_evidence",
            "classification_task": "multiclass_transaction_type",
            "runtime_policy": "evidence_only_rules_remain_source_of_truth",
            "semantic_note": (
                "transaction_type describes money-flow semantics such as purchase, "
                "salary, refund or transfer. Expense category remains a separate "
                "budget taxonomy predicted by the category classifier."
            ),
        }
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV with transaction_type silver labels.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    df = pd.read_csv(args.csv)
    report = build_evidence_report(df)
    out = args.out
    if out is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = REPORTS_DIR / f"transaction_type_classification_{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote transaction-type evidence to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
