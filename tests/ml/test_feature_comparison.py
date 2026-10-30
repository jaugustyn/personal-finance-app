"""Shared feature experiments, metric contracts and provenance regressions."""
from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from finance.ml.classification import candidate_evaluation, feature_comparison
from finance.ml.classification.candidate_evaluation import (
    ValidationSplitNotFeasible,
    development_split_ids,
)
from finance.ml.classification.metrics import calibration_metrics, prediction_metrics
from scripts import compare_classification_features as command


def synthetic_frame() -> pd.DataFrame:
    """360 synthetic labels, multiple merchant groups and occasional ambiguous text."""
    rows = []
    merchants = ["alpha", "beta", "gamma", "delta", "omega"]
    for repetition in range(120):
        for index, (label, word) in enumerate([
            ("food", "pieczywo"), ("transport", "paliwo"), ("health", "apteka"),
        ]):
            detail = word if repetition % 7 else "terminal"
            merchant = f"{merchants[repetition % 5]} {detail} synthetic"
            title = "zakup" if repetition % 7 else "platnosc"
            booked = date(2025, 1, 1) + timedelta(days=repetition)
            rows.append({
                "transaction_id": len(rows) + 1,
                "category": label,
                "category_confirmation_method": "manual",
                "category_confirmed_at": datetime(2026, 1, 1, tzinfo=UTC),
                "category_origin_ref": None,
                "merchant": merchant,
                "title": title,
                "text": f"{merchant} {title}",
                "abs_amount": float(30 + repetition % 20 + index),
                "day_of_week": booked.weekday(),
                "booking_date": booked,
                "source": "generic" if repetition % 2 else "pekao",
                "direction": "debit",
                "transaction_type": "expense",
                "is_transfer": False,
            })
    return pd.DataFrame(rows)


def test_metrics_keep_weighted_f1_and_label_order() -> None:
    result = prediction_metrics(
        np.asarray(["food", "food", "food", "transport"]),
        np.asarray(["food", "food", "transport", "transport"]),
        labels=["transport", "food"],
    )
    assert result["n"] == 4
    assert result["macro_f1"] == pytest.approx((0.8 + 2 / 3) / 2)
    assert result["weighted_f1"] == pytest.approx((3 * 0.8 + 2 / 3) / 4)
    assert result["confusion_matrix"] == [[1, 0], [1, 2]]
    calibration = calibration_metrics(
        np.asarray(["food", "transport"]), np.asarray(["food", "transport"]),
        np.asarray([[0.8, 0.2], [0.3, 0.7]]), np.asarray(["food", "transport"]),
    )
    assert calibration["log_loss"] == pytest.approx(-(math.log(0.8) + math.log(0.7)) / 2)
    assert calibration["brier_multiclass"] == pytest.approx(0.13)
    assert calibration["ece"] == pytest.approx(0.25)
    assert sum(item["count"] for item in calibration["reliability_bins"]) == 2


def test_comparison_is_reproducible_and_keeps_validation_out_of_training(monkeypatch) -> None:
    frame = synthetic_frame()
    splits = development_split_ids(frame)
    reserved = set().union(*splits.values())
    frame.loc[frame.transaction_id.isin(reserved), "text"] += " validationonlytoken"
    monkeypatch.setattr(candidate_evaluation, "_latency_p99_ms", lambda *_args: 1.0)
    real_evaluate = feature_comparison.evaluate_candidate
    evaluated = []

    def evaluate(data, **kwargs):
        assert kwargs["split_ids"] == splits
        result = real_evaluate(data, **kwargs)
        text = result.pipeline.named_steps["features"].named_transformers_["text"]
        word_vectorizer = dict(text.transformer_list)["word"]
        assert "validationonlytoken" not in word_vectorizer.vocabulary_
        if kwargs["feature_set"] == "feature_v2":
            assert result.gates["technical"]["passed"]
            assert not result.gates["promotable"]
            assert result.gates["level"] == "benchmark_only"
        evaluated.append((kwargs["estimator"], kwargs["feature_set"]))
        return result

    monkeypatch.setattr(feature_comparison, "evaluate_candidate", evaluate)
    report = feature_comparison.compare_features(frame, split_ids=splits, data_source="synthetic")
    repeated = feature_comparison.compare_features(
        frame.sample(frac=1, random_state=7), split_ids=splits, data_source="synthetic",
    )
    assert evaluated[:4] == [
        ("logreg", "baseline"), ("logreg", "feature_v2"),
        ("linear_svc_calibrated", "baseline"), ("linear_svc_calibrated", "feature_v2"),
    ]
    assert report["variants"] == repeated["variants"]
    assert report["training_fingerprint"] == repeated["training_fingerprint"]
    assert report["dataset_fingerprint"] == repeated["dataset_fingerprint"]
    assert report["split_fingerprints"] == repeated["split_fingerprints"]
    assert report["evaluation_role"] == "development_validation"
    assert report["protocol"]["final_test_evaluated"] is False
    for variant in report["variants"]:
        metrics = variant["metrics"]
        for name in ("time", "merchant", "oof"):
            assert sum(map(sum, metrics[name]["confusion_matrix"])) == metrics[name]["n"]
            assert metrics[name]["weighted_f1"] > 0.5
            assert metrics[name]["macro_f1"] > 0.5
            assert 0 <= metrics[name]["calibration"]["ece"] <= 1
        assert metrics["oof"]["n"] == report["training_rows"]
    for index, estimator in enumerate(("logreg", "linear_svc_calibrated")):
        baseline = report["variants"][2 * index]["metrics"]
        extended = report["variants"][2 * index + 1]["metrics"]
        for name in ("time", "merchant"):
            assert report["feature_v2_minus_baseline"][estimator][name]["macro_f1"] == (
                extended[name]["macro_f1"] - baseline[name]["macro_f1"]
            )
    serialized = json.dumps(report, allow_nan=False)
    assert "alpha pieczywo synthetic" not in serialized
    assert "validationonlytoken" not in serialized
    assert "transaction_id\"" not in serialized


@pytest.mark.parametrize("method, confirmed_at, origin", [
    (None, None, None),
    ("personal_rule_auto", datetime(2026, 1, 1, tzinfo=UTC), "personal_rule:1"),
    ("accepted_suggestion", datetime(2026, 1, 1, tzinfo=UTC), None),
    ("accepted_suggestion", datetime(2026, 1, 1, tzinfo=UTC), " "),
    ("manual", None, None),
])
def test_invalid_holdout_provenance_stops_before_fitting(monkeypatch, method, confirmed_at, origin):
    frame = synthetic_frame()
    splits = development_split_ids(frame)
    selected = frame.transaction_id == min(splits["time"])
    frame.loc[selected, "category_confirmation_method"] = method
    frame.loc[selected, "category_confirmed_at"] = confirmed_at
    frame.loc[selected, "category_origin_ref"] = origin
    monkeypatch.setattr(
        feature_comparison, "evaluate_candidate",
        lambda *_args, **_kwargs: pytest.fail("Invalid provenance reached model fitting"),
    )
    with pytest.raises(ValidationSplitNotFeasible, match="missing rows"):
        feature_comparison.compare_features(frame, split_ids=splits, data_source="synthetic")


def test_duplicate_transaction_identity_stops_before_fitting() -> None:
    frame = synthetic_frame()
    splits = development_split_ids(frame)
    with pytest.raises(ValueError, match="unique"):
        feature_comparison.compare_features(
            pd.concat([frame, frame.iloc[[0]]]), split_ids=splits, data_source="synthetic",
        )


@pytest.mark.parametrize("has_frozen_set", [False, True])
def test_command_rejects_absent_or_invalid_frozen_set(db_session, monkeypatch, tmp_path, has_frozen_set):
    monkeypatch.setattr(command, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        command, "current_evaluation_set",
        lambda _session: SimpleNamespace(id="test-set") if has_frozen_set else None,
    )
    monkeypatch.setattr(command, "load_training_set", lambda _session: synthetic_frame())
    monkeypatch.setattr(command, "validate_evaluation_set", lambda *_args: False)
    monkeypatch.setattr(
        command, "compare_features", lambda *_args, **_kwargs: pytest.fail("Invalid split used"),
    )
    output = tmp_path / "comparison.json"
    with pytest.raises(SystemExit) as error:
        command.main(["--from-db", "--output", str(output)])
    assert error.value.code == 2
    assert not output.exists()
