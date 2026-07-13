"""Regression tests for label provenance, frozen holdouts and lifecycle gates."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from finance.domain.enums import Category
from finance.domain.models import MlModelVersion, MlTrainingJob, Transaction
from finance.llm import client as llm_client
from finance.ml.classification import lifecycle
from finance.ml.classification.artifacts import (
    build_model_artifact,
    require_compatible_artifact,
    require_runtime_artifact,
    runtime_versions,
)
from finance.ml.classification.candidate_evaluation import (
    CandidateEvaluation,
    ValidationSplitNotFeasible,
    candidate_variants,
    derive_confidence_policy,
    development_split_ids,
    evaluate_candidate,
    full_matrix_variants,
    supported_classification_rows,
)
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.evaluation_sets import (
    dataset_fingerprint,
    evaluation_set_summary,
    freeze_evaluation_set,
    invalidate_for_label_change,
)
from finance.ml.classification.lifecycle import (
    TrainingJobConflict,
    _artifact_sha256,
    activate_model_version,
    enqueue_training_job,
    run_training_job,
    training_data_preflight,
)
from finance.ml.classification.status_comparison import recommend_model


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


def test_routine_training_uses_two_baseline_candidates() -> None:
    assert candidate_variants() == [
        ("logreg", "baseline"),
        ("linear_svc_calibrated", "baseline"),
    ]


def test_feature_v2_is_benchmark_only() -> None:
    with pytest.raises(ValueError, match="benchmark-only"):
        candidate_variants("logreg", "feature_v2")


def test_full_matrix_keeps_eight_research_only_benchmarks() -> None:
    variants = full_matrix_variants()

    assert len(variants) == 10
    assert sum(1 for _, _, promotable in variants if promotable) == 2
    assert sum(1 for _, _, promotable in variants if not promotable) == 8


def test_300_labels_can_train_supported_subset_of_ontology() -> None:
    rows = []
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
        "omega",
    ]
    categories = [
        "transport" if index % 15 == 0 else "food" for index in range(300)
    ] + ["health"] * 5
    category_counts: dict[str, int] = {}
    for index, category in enumerate(categories):
        category_index = category_counts.get(category, 0)
        category_counts[category] = category_index + 1
        rows.append(
            {
                "transaction_id": index + 1,
                "category": category,
                "merchant": (
                    f"{merchants[category_index % len(merchants)]} {category}"
                ),
                "title": category,
                "text": category,
                "abs_amount": 10.0,
                "day_of_week": index % 7,
                "booking_date": date(2025, 1, 1) + timedelta(days=index),
                "source": "pekao",
                "direction": "debit",
                "transaction_type": "expense",
                "is_transfer": False,
            }
        )
    frame = pd.DataFrame(rows).sort_values(
        ["booking_date", "transaction_id"], kind="stable"
    )
    supported, labels, counts, unsupported = supported_classification_rows(frame)

    assert len(frame) >= 300
    assert labels == ["food", "transport"]
    assert set(supported["category"]) == {"food", "transport"}
    assert counts["health"] == 5
    assert unsupported["health"] == 5
    assert training_data_preflight(frame)["ready"] is True


def test_validation_split_error_reports_class_counts() -> None:
    frame = pd.DataFrame(
        [
            {
                "transaction_id": index + 1,
                "category": "food" if index < 290 else "transport",
                "merchant": f"merchant-{index % 5}",
                "title": "purchase",
                "booking_date": date(2025, 1, 1) + timedelta(days=index),
            }
            for index in range(300)
        ]
    )

    with pytest.raises(
        ValidationSplitNotFeasible,
        match="validation_split_not_feasible.*counts=",
    ):
        development_split_ids(frame)


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
    assert result.confidence_policy == {
        "source": "fixed_runtime_threshold",
        "default_threshold": 0.55,
        "per_category": {},
        "allow_other_accept": False,
    }
    assert result.confidence_diagnostics["source"] == "real_oof_predictions"
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

    old = dict(artifact)
    old["schema_version"] = "2.1"
    old["metadata"] = dict(artifact["metadata"]) | {
        "artifact_schema_version": "2.1"
    }
    with pytest.raises(ValueError, match="artifact_schema_version_mismatch"):
        require_runtime_artifact(old)


def test_runtime_artifact_rejects_feature_v2_and_dynamic_thresholds() -> None:
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="feature_v2",
        pipeline=_Pipeline(),
        report={},
    )
    with pytest.raises(ValueError, match="feature_set_not_promotable"):
        require_runtime_artifact(artifact)

    artifact["feature_set"] = "baseline"
    artifact["confidence_policy"] = {
        "default_threshold": 0.7,
        "per_category": {"food": {"threshold": 0.8}},
        "allow_other_accept": False,
    }
    with pytest.raises(ValueError, match="runtime_policy_mismatch"):
        require_runtime_artifact(artifact)


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
        enqueue_training_job(db_session, estimator="logreg", feature_set="baseline")


def test_training_job_separates_candidates_from_research_benchmarks(db_session) -> None:
    routine = enqueue_training_job(db_session)

    assert routine.requested_variants == [
        {
            "estimator": "logreg",
            "feature_set": "baseline",
            "promotable": True,
        },
        {
            "estimator": "linear_svc_calibrated",
            "feature_set": "baseline",
            "promotable": True,
        },
    ]
    assert all(item["promotable"] for item in routine.requested_variants)

    routine.status = "completed"
    routine.execution_slot = None
    db_session.commit()
    experiment = enqueue_training_job(db_session, include_benchmarks=True)

    assert len(experiment.requested_variants) == 10
    assert sum(not item["promotable"] for item in experiment.requested_variants) == 8


def test_dataset_fingerprint_tracks_features_and_ignores_row_order() -> None:
    frame = pd.DataFrame(
        [
            {
                "transaction_id": 2,
                "category": "transport",
                "category_confirmation_method": "manual",
                "category_confirmed_at": datetime(2026, 1, 2, tzinfo=UTC),
                "booking_date": date(2026, 1, 2),
                "merchant": "Orlen",
                "title": "Paliwo",
                "abs_amount": 200.0,
                "day_of_week": 4,
                "source": "pekao",
                "direction": "debit",
                "transaction_type": "expense",
            },
            {
                "transaction_id": 1,
                "category": "food",
                "category_confirmation_method": "accepted_suggestion",
                "category_confirmed_at": datetime(2026, 1, 1, tzinfo=UTC),
                "booking_date": date(2026, 1, 1),
                "merchant": "Lidl",
                "title": "Zakupy",
                "abs_amount": 50.0,
                "day_of_week": 3,
                "source": "pekao",
                "direction": "debit",
                "transaction_type": "expense",
            },
        ]
    )

    original = dataset_fingerprint(frame)

    assert dataset_fingerprint(frame.iloc[::-1].reset_index(drop=True)) == original
    changed = frame.copy()
    changed.loc[changed["transaction_id"] == 1, "title"] = "Inne zakupy"
    assert dataset_fingerprint(changed) != original


def test_recommendation_matches_exact_model_version() -> None:
    rows = [
        {
            "model_id": "new-model",
            "estimator": "logreg",
            "feature_set": "baseline",
            "rank": 1,
            "skipped": False,
        },
        {
            "model_id": "old-model",
            "estimator": "logreg",
            "feature_set": "baseline",
            "rank": 2,
            "skipped": False,
        },
    ]
    status = {
        "exists": True,
        "model_version_id": "old-model",
        "compatibility_warnings": [],
    }

    recommendation = recommend_model(rows, status, {})

    assert recommendation["model_id"] == "new-model"
    assert rows[0]["is_recommended"] is True
    assert rows[1]["is_recommended"] is False
    assert "activate_recommended" in recommendation["action_codes"]
    assert "current_matches_recommended" not in recommendation["action_codes"]


def test_training_job_registers_ranked_candidates_and_recommendation(
    db_engine,
    tmp_path,
    monkeypatch,
) -> None:
    session_factory = sessionmaker(bind=db_engine, future=True)
    with session_factory() as session:
        job_id = enqueue_training_job(session).id

    frame = pd.DataFrame(
        [
            {
                "transaction_id": 1,
                "category": "food",
                "category_confirmation_method": "manual",
                "category_confirmed_at": datetime(2026, 1, 1, tzinfo=UTC),
                "booking_date": date(2026, 1, 1),
                "merchant": "Lidl",
                "title": "Zakupy",
                "abs_amount": 20.0,
                "day_of_week": 3,
                "source": "pekao",
                "direction": "debit",
                "transaction_type": "expense",
            }
        ]
    )

    def evaluation(estimator: str) -> CandidateEvaluation:
        score = 0.72 if estimator == "logreg" else 0.68
        slice_metrics = {
            "macro_f1": score,
            "weighted_f1": score,
            "coverage": 0.8,
            "accuracy_on_covered": 0.9,
            "confusion_matrix": [[1, 0], [0, 1]],
        }
        return CandidateEvaluation(
            estimator=estimator,
            feature_set="baseline",
            pipeline=_Pipeline(),
            metrics={
                "time": slice_metrics,
                "merchant": slice_metrics,
                "oof": {},
                "p99_ms": 1.0,
                "labels": ["food", "transport"],
                "ranking": {
                    "worst_macro_f1": score,
                    "mean_macro_f1": score,
                    "mean_covered_accuracy": 0.9,
                },
            },
            confidence_policy={
                "source": "fixed_runtime_threshold",
                "default_threshold": 0.55,
                "per_category": {},
                "allow_other_accept": False,
            },
            confidence_diagnostics={},
            gates={
                "technical": {"passed": True, "checks": {}},
                "thesis": {"passed": False, "checks": {}},
                "promotable": True,
                "level": "technical",
            },
        )

    monkeypatch.setattr(lifecycle, "CANDIDATES_DIR", tmp_path / "models")
    monkeypatch.setattr(lifecycle, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(lifecycle, "load_training_set", lambda _session: frame)
    monkeypatch.setattr(
        lifecycle,
        "development_split_ids",
        lambda _df: {"time": {1}, "merchant": {1}},
    )
    monkeypatch.setattr(
        lifecycle,
        "evaluate_candidate",
        lambda _df, *, estimator, **_kwargs: evaluation(estimator),
    )

    run_training_job(session_factory=session_factory, job_id=job_id)

    with session_factory() as session:
        job = session.get(MlTrainingJob, job_id)
        versions = list(
            session.execute(
                select(MlModelVersion)
                .where(MlModelVersion.job_id == job_id)
                .order_by(MlModelVersion.created_at)
            ).scalars()
        )
        assert job is not None
        assert job.status == "completed"
        assert len(versions) == 2
        by_estimator = {version.estimator: version for version in versions}
        assert job.result["recommended_model_id"] == by_estimator["logreg"].id
        assert by_estimator["logreg"].status == "candidate"
        assert by_estimator["linear_svc_calibrated"].status == "candidate"


def test_research_benchmark_job_rejects_candidate_filters(db_session) -> None:
    with pytest.raises(ValueError, match="cannot be combined"):
        enqueue_training_job(
            db_session,
            estimator="logreg",
            include_benchmarks=True,
        )


def test_active_model_is_not_a_regression_gate_without_frozen_evaluation_set(
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
    monkeypatch.setattr(
        lifecycle,
        "evaluate_pipeline_slices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("active model should not be a gate")
        ),
    )
    frame = pd.DataFrame([{"transaction_id": 1}])
    split_ids = {"time": {1}, "merchant": {1}}

    result = lifecycle._active_comparison(
        db_session,
        df=frame,
        split_ids=split_ids,
        evaluation_set_id=None,
    )

    assert result is None


def test_broken_active_model_does_not_block_unfrozen_training(db_session, tmp_path) -> None:
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

    assert (
        lifecycle._active_comparison(
            db_session,
            df=pd.DataFrame([{"transaction_id": 1}]),
            split_ids={"time": {1}, "merchant": {1}},
            evaluation_set_id=None,
        )
        is None
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
