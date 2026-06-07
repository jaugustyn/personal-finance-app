"""Coverage tests for finance.ml.classification.train.

Avoids the heavy CLI / DB / persistence paths; exercises the pure helpers and
the cross-validated evaluate() loop on a tiny synthetic dataset.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finance.ml.classification import train


def _tiny_labelled_df() -> pd.DataFrame:
    rows: list[dict] = []
    # 2 classes × 5 rows: enough for n_splits=2 stratified CV.
    for i in range(5):
        rows.append({
            "text": f"BIEDRONKA zakupy {i}",
            "abs_amount": 30.0 + i,
            "day_of_week": i % 7,
            "category": "food",
            "source": "synthetic",
        })
        rows.append({
            "text": f"ORLEN paliwo {i}",
            "abs_amount": 200.0 + i,
            "day_of_week": (i + 2) % 7,
            "category": "transport",
            "source": "synthetic",
        })
    return pd.DataFrame(rows)


def test_filter_rare_classes_drops_singletons() -> None:
    df = pd.DataFrame({
        "category": ["food", "food", "food", "rare"],
        "text": ["a"] * 4,
        "abs_amount": [1.0] * 4,
        "day_of_week": [0] * 4,
    })
    kept, dropped = train._filter_rare_classes(df)
    assert "rare" in dropped
    assert (kept["category"] == "food").all()


def test_build_label_readiness_reports_data_targets() -> None:
    df = _tiny_labelled_df()
    readiness = train.build_label_readiness(df)

    assert readiness["level"] == "insufficient"
    assert readiness["total_labelled"] == len(df)
    assert readiness["minimum_total"] == 300
    assert readiness["recommended_total"] == 800
    assert readiness["ideal_total"] == 2000
    assert readiness["category_predicted_is_ground_truth"] is False
    assert readiness["category_counts"]["food"] == 5
    assert "health" in readiness["below_minimum_per_category"]


def test_filter_category_training_rows_excludes_transfers_and_non_candidates() -> None:
    df = pd.DataFrame(
        {
            "text": [
                "shop",
                "allegro",
                "own transfer",
                "person transfer",
                "salary",
                "income",
                "credit with category",
            ],
            "abs_amount": [10.0, 120.0, 100.0, 50.0, 5000.0, 700.0, 300.0],
            "day_of_week": [1, 1, 1, 1, 1, 1, 1],
            "category": [
                "food",
                "shopping",
                "other",
                "other",
                "other",
                "other",
                "shopping",
            ],
            "transaction_type": [
                "purchase",
                "purchase",
                "own_transfer",
                "person_transfer",
                "salary",
                "income",
                "purchase",
            ],
            "is_transfer": [False, False, True, False, False, False, False],
            "direction": [
                "debit",
                "debit",
                "debit",
                "debit",
                "credit",
                "credit",
                "credit",
            ],
        }
    )

    filtered = train.filter_category_training_rows(df)

    assert filtered["text"].tolist() == ["shop", "allegro"]


def test_evaluate_returns_metrics_per_estimator() -> None:
    df = _tiny_labelled_df()
    report = train.evaluate(df, n_splits=2)
    assert report["n_total_labelled"] == len(df)
    assert report["n_classes"] == 2
    assert "models" in report and len(report["models"]) >= 1
    for _name, info in report["models"].items():
        assert 0.0 <= info["macro_f1"] <= 1.0
        assert 0.0 <= info["weighted_f1"] <= 1.0
        assert "report" in info
        assert "confusion_matrix" in info
        assert "confidence_curve" in info
        assert "per_category" in info
        assert "confusion_hotspots" in info
        assert "recommended_thresholds_by_category" in info


def test_build_evidence_report_includes_real_and_augmented() -> None:
    df = _tiny_labelled_df()
    synth = df.copy()
    report = train.build_evidence_report(df, augmented_df=synth, n_splits=2)
    assert report["selected_experiment"] == "real_only"
    assert report["selected_experiment_note"]
    assert set(report["experiments"]) == {"real_only", "augmented"}
    assert set(report["feature_variants"]) == {"baseline", "feature_v2"}
    assert report["feature_decision"]["recommended_feature_set"] in {
        "baseline",
        "feature_v2",
    }
    assert set(report["validation_slices"]) == {
        "stratified_cv",
        "time_holdout",
        "merchant_group_holdout",
    }
    assert "confidence_policy" in report
    assert "per_category" in next(iter(report["models"].values()))
    assert report["label_readiness"]["training_labels_source"] == (
        "confirmed Transaction.category only"
    )
    assert report["target_macro_f1"] == 0.75


def test_build_evidence_report_includes_external_experiments() -> None:
    df = _tiny_labelled_df()
    external = _tiny_labelled_df()
    external["source"] = "external_kaggle_personal_finance"

    report = train.build_evidence_report(df, external_df=external, n_splits=2)

    assert report["selected_experiment"] == "real_only"
    assert {"external_only", "real_plus_external"}.issubset(report["experiments"])
    assert report["external_data"]["provided"] is True
    assert report["external_data"]["n_labelled"] == len(external)
    assert report["external_data_note"]


def test_evaluate_feature_v2_returns_metrics() -> None:
    df = _tiny_labelled_df()
    df["merchant"] = ["Biedronka", "Orlen"] * 5
    df["booking_date"] = pd.date_range("2026-01-01", periods=len(df), freq="D")
    df["transaction_type"] = "purchase"
    report = train.evaluate_feature_v2(df, n_splits=2)
    assert "linear_svc" in report["models"]


def test_validation_slices_include_time_and_merchant_holdouts() -> None:
    df = _tiny_labelled_df()
    df["merchant"] = ["Biedronka", "Orlen"] * 5
    df["booking_date"] = pd.date_range("2026-01-01", periods=len(df), freq="D")

    slices = train.build_validation_slices(df)

    assert "stratified_cv" in slices
    assert "time_holdout" in slices
    assert "merchant_group_holdout" in slices
    assert slices["time_holdout"]["split"] == "last_20_percent_by_booking_date"
    if not slices["merchant_group_holdout"].get("skipped"):
        assert slices["merchant_group_holdout"]["merchant_group_overlap"] == 0


def test_evaluate_raises_on_empty() -> None:
    empty = pd.DataFrame({"category": [None, None], "text": ["x", "y"],
                          "abs_amount": [1.0, 1.0], "day_of_week": [0, 0]})
    with pytest.raises(SystemExit):
        train.evaluate(empty)


def test_fit_final_returns_fitted_pipeline() -> None:
    df = _tiny_labelled_df()
    pipe = train.fit_final(df, "linear_svc")
    preds = pipe.predict(train.to_features(df.head(2)))
    assert len(preds) == 2


def test_fit_final_filters_non_category_training_rows() -> None:
    df = _tiny_labelled_df()
    df["direction"] = "debit"
    df["transaction_type"] = "purchase"
    income_rows = pd.DataFrame(
        [
            {
                "text": "ACME wynagrodzenie",
                "abs_amount": 5000.0,
                "day_of_week": 1,
                "category": "other",
                "direction": "credit",
                "transaction_type": "income",
            },
            {
                "text": "WSEI stypendium",
                "abs_amount": 1200.0,
                "day_of_week": 2,
                "category": "other",
                "direction": "credit",
                "transaction_type": "income",
            },
        ]
    )

    pipe = train.fit_final(pd.concat([df, income_rows], ignore_index=True), "linear_svc")

    assert "other" not in set(pipe.named_steps["clf"].classes_)


def test_fit_final_feature_v2_returns_fitted_pipeline() -> None:
    df = _tiny_labelled_df()
    df["merchant"] = ["Biedronka", "Orlen"] * 5
    df["booking_date"] = pd.date_range("2026-01-01", periods=len(df), freq="D")
    df["transaction_type"] = "purchase"
    pipe = train.fit_final(df, "linear_svc", feature_set="feature_v2")
    preds = pipe.predict(train.to_features_v2(df.head(2)))
    assert len(preds) == 2


def test_guess_source_pekao_revolut_and_unknown() -> None:
    from finance.domain.enums import BankSource

    assert train._guess_source(Path("pekao_2026.csv")) is BankSource.PEKOA \
        if hasattr(BankSource, "PEKOA") else \
        train._guess_source(Path("pekao_2026.csv")) is BankSource.PEKAO
    assert train._guess_source(Path("revolut-account-statement.csv")) is BankSource.REVOLUT
    with pytest.raises(ValueError):
        train._guess_source(Path("mystery.csv"))


def test_load_synthetic_validates_columns(tmp_path: Path) -> None:
    good = tmp_path / "synth.csv"
    good.write_text("text,abs_amount,day_of_week,category\nfoo,10,1,food\n")
    df = train._load_synthetic(good)
    assert df.iloc[0]["category"] == "food"
    assert (df["source"] == "synthetic").all()

    bad = tmp_path / "bad.csv"
    bad.write_text("text,category\nfoo,food\n")
    with pytest.raises(ValueError):
        train._load_synthetic(bad)
