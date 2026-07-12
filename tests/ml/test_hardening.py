"""Regression tests for label provenance, frozen holdouts and lifecycle gates."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

from finance.domain.enums import Category
from finance.domain.models import MlModelVersion, Transaction
from finance.llm import client as llm_client
from finance.ml.classification import lifecycle
from finance.ml.classification.artifacts import (
    build_model_artifact,
    require_compatible_artifact,
    runtime_versions,
)
from finance.ml.classification.candidate_evaluation import (
    candidate_variants,
    derive_confidence_policy,
    development_split_ids,
    evaluate_candidate,
    full_matrix_variants,
)
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.evaluation_sets import (
    evaluation_set_summary,
    freeze_evaluation_set,
    invalidate_for_label_change,
)
from finance.ml.classification.lifecycle import (
    TrainingJobConflict,
    _artifact_sha256,
    activate_model_version,
    enqueue_training_job,
    training_data_preflight,
)


class _Pipeline:
    classes_ = np.asarray(["food", "transport"])

    def predict(self, _frame):
        return np.asarray(["food"])

    def predict_proba(self, _frame):
        return np.asarray([[0.9, 0.1]])


def _transaction(index: int, *, category: str | None, confirmed: bool) -> Transaction:
    return Transaction(
        booking_date=date(2026, 1, 1) + timedelta(days=index),
        amount=Decimal("-10"),
        amount_base=Decimal("-10"),
        base_currency="PLN",
        currency="PLN",
        direction="debit",
        merchant=f"Merchant {index}",
        title="purchase",
        category=category,
        category_source="manual" if confirmed else "bank",
        category_confirmation_method="manual" if confirmed else None,
        category_confirmed_at=datetime.now(UTC) if confirmed else None,
        source="pekao",
        transaction_type="expense",
        is_transfer=False,
        dedup_hash=f"hardening-{index}",
    )


def test_db_training_set_contains_only_confirmed_system_categories(db_session) -> None:
    personal_auto = _transaction(4, category="health", confirmed=True)
    personal_auto.category_confirmation_method = "personal_rule_auto"
    db_session.add_all(
        [
            _transaction(1, category="food", confirmed=True),
            _transaction(2, category="transport", confirmed=False),
            _transaction(3, category="my_custom_category", confirmed=True),
            personal_auto,
        ]
    )
    db_session.commit()

    frame = load_training_set(db_session)

    assert frame["category"].tolist() == ["food"]
    assert frame.iloc[0]["category_confirmation_method"] == "manual"


def test_confidence_policy_requires_support_and_never_fabricates_probability() -> None:
    truth = np.asarray(["food"] * 30 + ["transport"] * 20)
    predicted = np.asarray(["food"] * 30 + ["transport"] * 20)
    confidence = np.linspace(0.40, 0.99, 50)

    policy = derive_confidence_policy(truth, predicted, confidence)

    assert policy["source"] == "real_oof_predictions"
    assert policy["global"]["covered"] >= 30
    assert policy["per_category"]["health"]["inherited_global"] is True
    assert policy["allow_other_accept"] is False


def test_benchmark_only_estimator_cannot_be_promoted() -> None:
    with pytest.raises(ValueError, match="benchmark-only"):
        candidate_variants("random_forest", "baseline")


def test_routine_training_uses_one_simple_candidate() -> None:
    assert candidate_variants() == [("logreg", "baseline")]


def test_full_matrix_keeps_six_research_only_benchmarks() -> None:
    variants = full_matrix_variants()

    assert len(variants) == 10
    assert sum(1 for _, _, promotable in variants if promotable) == 4
    assert sum(1 for _, _, promotable in variants if not promotable) == 6


def test_candidate_uses_both_primary_holdouts_and_reports_calibration() -> None:
    rows = []
    transaction_id = 1
    merchant_names = ["alpha", "beta", "gamma", "delta", "omega"]
    for repetition in range(40):
        for category in Category:
            rows.append(
                {
                    "transaction_id": transaction_id,
                    "text": f"{category.value} merchant {category.value} purchase",
                    "merchant": (
                        f"{merchant_names[repetition % len(merchant_names)]} "
                        f"{category.value}"
                    ),
                    "title": f"{category.value} purchase",
                    "abs_amount": 10.0 + repetition,
                    "day_of_week": repetition % 7,
                    "booking_date": date(2025, 1, 1) + timedelta(days=repetition),
                    "source": "pekao",
                    "transaction_type": "expense",
                    "direction": "debit",
                    "is_transfer": False,
                    "category": category.value,
                }
            )
            transaction_id += 1
    frame = pd.DataFrame(rows)
    assert training_data_preflight(frame)["ready"] is True
    split_ids = development_split_ids(frame)

    result = evaluate_candidate(
        frame,
        estimator="logreg",
        feature_set="baseline",
        split_ids=split_ids,
        frozen_evaluation_set=False,
    )

    assert result.metrics["time"]["macro_f1"] > 0.90
    assert result.metrics["merchant"]["macro_f1"] > 0.90
    assert "brier_multiclass" in result.metrics["oof"]["calibration"]
    assert result.gates["technical"]["passed"] is True
    assert result.gates["thesis"]["passed"] is False


def test_artifact_requires_exact_locked_versions() -> None:
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="baseline",
        pipeline=_Pipeline(),
        report={},
    )
    require_compatible_artifact(artifact)
    incompatible = runtime_versions() | {"joblib": "0.0"}
    with pytest.raises(ValueError, match="joblib_version_mismatch"):
        require_compatible_artifact(artifact, current_versions=incompatible)


def test_ollama_url_is_restricted_to_local_hosts(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(ollama_base_url="https://external.example:11434"),
    )
    with pytest.raises(llm_client.OllamaUnavailable, match="locally"):
        llm_client.validated_base_url()


def test_training_job_uses_single_durable_slot(db_session) -> None:
    first = enqueue_training_job(db_session, estimator="logreg", feature_set="baseline")
    assert first.status == "queued"
    with pytest.raises(TrainingJobConflict):
        enqueue_training_job(db_session, estimator="logreg", feature_set="feature_v2")


def test_training_job_separates_candidates_from_research_benchmarks(db_session) -> None:
    routine = enqueue_training_job(db_session)

    assert routine.requested_variants == [
        {
            "estimator": "logreg",
            "feature_set": "baseline",
            "promotable": True,
        }
    ]
    assert all(item["promotable"] for item in routine.requested_variants)

    routine.status = "completed"
    routine.execution_slot = None
    db_session.commit()
    experiment = enqueue_training_job(db_session, include_benchmarks=True)

    assert len(experiment.requested_variants) == 10
    assert sum(not item["promotable"] for item in experiment.requested_variants) == 6


def test_research_benchmark_job_rejects_candidate_filters(db_session) -> None:
    with pytest.raises(ValueError, match="cannot be combined"):
        enqueue_training_job(
            db_session,
            estimator="logreg",
            include_benchmarks=True,
        )


def test_active_model_is_re_evaluated_when_dataset_fingerprint_changes(
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "active.joblib"
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="baseline",
        pipeline=_Pipeline(),
        report={},
        model_version_id="active-model",
        dataset_fingerprint="old-fingerprint",
        confidence_policy={"default_threshold": 0.55},
    )
    joblib.dump(artifact, path)
    db_session.add(
        MlModelVersion(
            id="active-model",
            estimator="logreg",
            feature_set="baseline",
            status="active",
            artifact_path=str(path),
            artifact_sha256=_artifact_sha256(path),
            dataset_fingerprint="old-fingerprint",
            metrics={},
            gates={"promotable": True},
            confidence_policy={"default_threshold": 0.55},
            promotable=True,
            activated_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    expected = {"time": {"macro_f1": 0.7}, "merchant": {"macro_f1": 0.8}}
    called: dict[str, object] = {}

    def fake_evaluate(frame, **kwargs):
        called["rows"] = len(frame)
        called["split_ids"] = kwargs["split_ids"]
        return expected

    monkeypatch.setattr(lifecycle, "evaluate_pipeline_slices", fake_evaluate)
    frame = pd.DataFrame([{"transaction_id": 1}])
    split_ids = {"time": {1}, "merchant": {1}}

    result = lifecycle._active_comparison(
        db_session,
        df=frame,
        split_ids=split_ids,
        evaluation_set_id=None,
    )

    assert result == expected
    assert called == {"rows": 1, "split_ids": split_ids}


def test_broken_active_model_blocks_regression_comparison(db_session, tmp_path) -> None:
    db_session.add(
        MlModelVersion(
            id="broken-active-model",
            estimator="logreg",
            feature_set="baseline",
            status="active",
            artifact_path=str(tmp_path / "missing.joblib"),
            artifact_sha256="0" * 64,
            dataset_fingerprint="fingerprint",
            metrics={},
            gates={"promotable": True},
            confidence_policy={"default_threshold": 0.55},
            promotable=True,
            activated_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    with pytest.raises(ValueError, match="regression baseline"):
        lifecycle._active_comparison(
            db_session,
            df=pd.DataFrame([{"transaction_id": 1}]),
            split_ids={"time": {1}, "merchant": {1}},
            evaluation_set_id=None,
        )


def test_activation_verifies_artifact_and_supports_rollback(
    db_session,
    tmp_path,
) -> None:
    rows = []
    for index in range(2):
        model_id = f"model-{index}"
        path = tmp_path / f"{model_id}.joblib"
        artifact = build_model_artifact(
            estimator="logreg",
            feature_set="baseline",
            pipeline=_Pipeline(),
            report={},
            model_version_id=model_id,
            dataset_fingerprint="fingerprint",
            confidence_policy={"default_threshold": 0.55},
        )
        joblib.dump(artifact, path)
        row = MlModelVersion(
            id=model_id,
            estimator="logreg",
            feature_set="baseline",
            status="candidate",
            artifact_path=str(path),
            artifact_sha256=_artifact_sha256(path),
            dataset_fingerprint="fingerprint",
            metrics={},
            gates={"promotable": True},
            confidence_policy={"default_threshold": 0.55},
            promotable=True,
        )
        db_session.add(row)
        rows.append(row)
    db_session.commit()

    activate_model_version(db_session, rows[0].id)
    activate_model_version(db_session, rows[1].id)
    rolled_back = activate_model_version(db_session, rows[0].id)

    assert rolled_back.status == "active"
    db_session.refresh(rows[1])
    assert rows[1].status == "archived"
    assert rolled_back.artifact_path == str(tmp_path / "model-0.joblib")
    assert not (tmp_path / "classifier_latest.joblib").exists()


def test_freeze_creates_versioned_private_slices_and_label_change_invalidates(
    db_session,
) -> None:
    start = date(2025, 1, 1)
    merchants = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "theta",
        "kappa",
        "lambda",
        "sigma",
        "omega",
        "atlas",
        "nova",
        "orion",
        "lumen",
    ]
    rows = []
    index = 0
    for category_index, category in enumerate(Category):
        for item in range(90):
            tx = _transaction(index, category=category.value, confirmed=True)
            tx.booking_date = start + timedelta(days=item * 5 + category_index % 5)
            tx.merchant = f"{merchants[item % len(merchants)]} store"
            rows.append(tx)
            index += 1
    db_session.add_all(rows)
    db_session.commit()

    evaluation_set = freeze_evaluation_set(db_session)
    summary = evaluation_set_summary(db_session)

    assert summary["active"] is True
    assert summary["time_count"] == 162
    assert summary["merchant_count"] > 0
    assert summary["excluded_training_count"] >= 162
    assert evaluation_set.config["min_per_category"] == 5

    assert invalidate_for_label_change(db_session, rows[-1].id) is True
    db_session.commit()
    assert evaluation_set_summary(db_session)["active"] is False
