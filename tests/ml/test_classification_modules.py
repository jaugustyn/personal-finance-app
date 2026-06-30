"""Focused tests for split category-classification modules."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finance.ml.classification import evaluation, fitting, reports, retrain
from finance.ml.classification.exceptions import (
    InsufficientClassSupport,
    NoLabelledRows,
    UnknownEstimator,
    UnknownFeatureSet,
)


def _labelled_df(rows_per_class: int = 5) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx in range(rows_per_class):
        rows.append(
            {
                "text": f"BIEDRONKA zakupy {idx}",
                "merchant": "Biedronka",
                "abs_amount": 30.0 + idx,
                "day_of_week": idx % 7,
                "booking_date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=idx),
                "category": "food",
                "direction": "debit",
                "transaction_type": "purchase",
                "is_transfer": False,
                "source": "synthetic",
            }
        )
        rows.append(
            {
                "text": f"ORLEN paliwo {idx}",
                "merchant": "Orlen",
                "abs_amount": 200.0 + idx,
                "day_of_week": (idx + 2) % 7,
                "booking_date": pd.Timestamp("2026-01-10") + pd.Timedelta(days=idx),
                "category": "transport",
                "direction": "debit",
                "transaction_type": "purchase",
                "is_transfer": False,
                "source": "synthetic",
            }
        )
    return pd.DataFrame(rows)


def test_evaluation_raises_domain_errors_for_invalid_training_sets() -> None:
    empty = pd.DataFrame(
        {
            "category": [None, None],
            "text": ["x", "y"],
            "abs_amount": [1.0, 2.0],
            "day_of_week": [0, 1],
        }
    )
    with pytest.raises(NoLabelledRows):
        evaluation.evaluate(empty)

    one_class = _labelled_df()
    one_class = one_class[one_class["category"] == "food"].reset_index(drop=True)
    with pytest.raises(InsufficientClassSupport):
        evaluation.evaluate(one_class, n_splits=2)


def test_fitting_validates_estimator_and_feature_set() -> None:
    df = _labelled_df()

    with pytest.raises(UnknownEstimator):
        fitting.fit_final(df, "missing_estimator")

    with pytest.raises(UnknownFeatureSet):
        fitting.fit_final(df, "linear_svc", feature_set="missing_features")


def test_reports_builds_evidence_without_train_facade() -> None:
    report = reports.build_evidence_report(_labelled_df(), n_splits=2)

    assert report["report_type"] == "classification_evidence"
    assert report["selected_experiment"] == "real_only"
    assert set(report["feature_variants"]) == {"baseline", "feature_v2"}
    assert "validation_slices" in report
    assert report["confidence_policy"]["default_threshold"] == 0.55


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, *_exc_info):
        return False


def test_retrain_aborts_before_persisting_with_too_few_labels(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        retrain,
        "load_training_set",
        lambda _session: _labelled_df(rows_per_class=1),
    )

    result = retrain.retrain_classifier(
        session_factory=_SessionContext,
        estimator="linear_svc",
        feature_set="baseline",
        model_path=tmp_path / "model.joblib",
        reports_dir=tmp_path / "reports",
    )

    assert result.status == "aborted"
    assert result.labelled_rows == 2
    assert result.model_path is None
    assert not (tmp_path / "model.joblib").exists()
    assert not (tmp_path / "reports").exists()


def test_retrain_persists_report_and_model_via_use_case(
    monkeypatch,
    tmp_path: Path,
) -> None:
    df = _labelled_df(rows_per_class=4)
    monkeypatch.setattr(retrain, "load_training_set", lambda _session: df)
    monkeypatch.setattr(
        retrain,
        "build_evidence_report",
        lambda _df: {
            "labels": ["food", "transport"],
            "models": {},
            "n_total_labelled": len(df),
            "n_classes": 2,
        },
    )
    monkeypatch.setattr(retrain, "fit_final", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        retrain.joblib,
        "dump",
        lambda _artifact, path: Path(path).write_text("artifact", encoding="utf-8"),
    )

    result = retrain.retrain_classifier(
        session_factory=_SessionContext,
        estimator="linear_svc",
        feature_set="baseline",
        model_path=tmp_path / "model.joblib",
        reports_dir=tmp_path / "reports",
    )

    assert result.status == "completed"
    assert result.labelled_rows == len(df)
    assert result.model_path == tmp_path / "model.joblib"
    assert result.report_path is not None
    assert result.report_path.exists()
    assert (tmp_path / "model.joblib").read_text(encoding="utf-8") == "artifact"
