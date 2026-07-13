"""API tests for classifier diagnostics and optional LLM fallback."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

from apps.api.routers import ml as ml_router
from finance.domain.models import (
    MlFeedbackEvent,
    MlModelVersion,
    MlTrainingJob,
    Transaction,
)
from finance.ml.classification import predict as predict_mod
from finance.ml.classification.artifacts import build_model_artifact
from finance.ml.classification.lifecycle import _artifact_sha256


def _artifact(*, confidence: float = 0.8) -> dict:
    return {
        "pipeline": _FakePipeline(confidence=confidence),
        "model_version_id": "api-test-model",
        "confidence_policy": {
            "source": "fixed_runtime_threshold",
            "default_threshold": 0.55,
            "per_category": {},
            "allow_other_accept": False,
        },
    }


class _FakePipeline:
    def __init__(self, *, category: str = "food", confidence: float = 0.8) -> None:
        self.category = category
        self.confidence = confidence
        self.classes_ = np.asarray(["food", "transport"])

    def predict(self, _x):
        return np.asarray([self.category])

    def predict_proba(self, _x):
        return np.asarray([[self.confidence, 1.0 - self.confidence]])


def _payload(**overrides):
    data = {
        "merchant": "Lidl",
        "title": "zakupy",
        "amount": str(Decimal("-42.10")),
        "booking_date": date(2026, 1, 10).isoformat(),
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _isolated_reports_dir(monkeypatch, tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(),
    )
    monkeypatch.setattr(
        predict_mod,
        "require_registered_active_artifact",
        lambda _session: _artifact(),
    )
    predict_mod.load_registered_artifact.cache_clear()
    return reports_dir


def _tx(session, **overrides) -> Transaction:
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-42.10"),
        currency="PLN",
        direction="debit",
        merchant="Lidl",
        title="zakupy",
        category="food",
        source="pekao",
        dedup_hash=f"ml-{len(session.new)}-{overrides.get('merchant', 'lidl')}",
        transaction_type="expense",
        is_transfer=False,
    )
    for key, value in overrides.items():
        setattr(tx, key, value)
    if tx.category is not None and "category_confirmation_method" not in overrides:
        tx.category_confirmation_method = "manual"
        tx.category_confirmed_at = datetime.now(UTC)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def _register_active_model(
    session,
    path,
    *,
    model_id: str,
    job_id: str | None = None,
    estimator: str = "linear_svc_calibrated",
) -> None:
    session.add(
        MlModelVersion(
            id=model_id,
            job_id=job_id,
            estimator=estimator,
            feature_set="baseline",
            status="active",
            artifact_path=str(path),
            artifact_sha256=_artifact_sha256(path),
            dataset_fingerprint="test-fingerprint",
            metrics={},
            gates={"promotable": True},
            confidence_policy={"default_threshold": 0.55},
            promotable=True,
            activated_at=datetime.now(UTC),
        )
    )
    session.commit()


def test_classify_returns_model_diagnostics(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.83),
    )

    response = client.post("/ml/classify", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["model_category"] == "food"
    assert body["confidence"] == 0.83
    assert body["source"] == "model"
    assert body["fallback_used"] is False
    assert body["threshold_used"] == 0.55
    assert body["recommended_action"] == "accept_candidate"
    assert body["classification_decision"]["action"] == "accept"
    assert body["classification_decision"]["threshold_used"] == 0.55
    assert body["top_predictions"][0]["category"] == "food"
    assert body["top_predictions"][0]["confidence"] == 0.83


def test_classify_low_confidence_does_not_fallback_by_default(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.51),
    )
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)

    response = client.post("/ml/classify", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["source"] == "model"
    assert body["fallback_used"] is False
    assert body["recommended_action"] == "review"
    assert body["classification_decision"]["action"] == "review"


def test_classify_marks_non_category_candidate(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.91),
    )

    response = client.post(
        "/ml/classify",
        json=_payload(transaction_type="income"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "not_category_candidate"
    assert body["classification_decision"]["action"] == "not_applicable"


def test_classify_infers_credit_amount_as_non_category_candidate(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.91),
    )

    response = client.post(
        "/ml/classify",
        json=_payload(amount="50.00"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "not_category_candidate"
    assert body["classification_decision"]["action"] == "not_applicable"


def test_classify_uses_fixed_threshold_from_artifact(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.83),
    )

    response = client.post("/ml/classify", json=_payload(threshold=0.99))

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "accept_candidate"
    assert body["threshold_used"] == 0.55
    assert body["classification_decision"]["action"] == "accept"
    assert "threshold" not in client.get("/openapi.json").json()["components"]["schemas"]["ClassifyRequest"]["properties"]


def test_classify_uses_valid_llm_fallback_when_enabled(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.51),
    )
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(
        predict_mod,
        "get_settings",
        lambda: SimpleNamespace(llm_fallback_enabled=True),
    )
    monkeypatch.setattr(
        predict_mod.llm_client,
        "chat",
        lambda **_kwargs: {"content": "transport"},
    )

    response = client.post(
        "/ml/classify",
        json=_payload(use_llm_fallback=True, threshold=0.55),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "transport"
    assert body["model_category"] == "food"
    assert body["source"] == "llm"
    assert body["confidence"] is None
    assert body["model_confidence"] == 0.51
    assert body["fallback_used"] is True


def test_classify_rejects_invalid_llm_category(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ml_router,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.51),
    )
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(
        predict_mod,
        "get_settings",
        lambda: SimpleNamespace(llm_fallback_enabled=True),
    )
    monkeypatch.setattr(
        predict_mod.llm_client,
        "chat",
        lambda **_kwargs: {"content": "groceries"},
    )

    response = client.post(
        "/ml/classify",
        json=_payload(use_llm_fallback=True, threshold=0.55),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["source"] == "model"
    assert body["fallback_used"] is False


def test_ml_status_reports_missing_model(client, monkeypatch, tmp_path) -> None:
    response = client.get("/ml/status")

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is False
    assert "shopping" in body["missing_categories"]
    assert body["classes"] == []
    assert body["compatibility_warnings"] == []


def test_ml_status_reports_artifact_metadata(
    client,
    db_session,
    monkeypatch,
    tmp_path,
) -> None:
    model_path = tmp_path / "registered-model.joblib"
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="baseline",
        pipeline=_FakePipeline(),
        model_version_id="active-status-model",
        report={
            "labels": ["food", "transport"],
            "n_total_labelled": 2,
            "n_classes": 2,
            "models": {
                "logreg": {
                    "macro_f1": 0.8,
                    "weighted_f1": 0.82,
                    "confidence_curve": [],
                    "skipped": False,
                }
            },
        },
    )
    joblib.dump(artifact, model_path)
    _register_active_model(
        db_session,
        model_path,
        model_id="active-status-model",
        estimator="logreg",
    )

    response = client.get("/ml/status")

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is True
    assert body["estimator"] == "logreg"
    assert body["artifact_metadata"]["artifact_schema_version"] == "3.0"
    assert "sklearn" in body["artifact_metadata"]["runtime_versions"]
    assert body["compatibility_warnings"] == []
    assert body["retrain_signal"]["retrain_recommended"] is False


def test_unregistered_latest_report_file_is_not_exposed(
    client,
    _isolated_reports_dir,
) -> None:
    report_path = _isolated_reports_dir / "classification_20260101_120000.json"
    report_path.write_text(json.dumps({"models": {}, "labels": ["food"]}), encoding="utf-8")

    response = client.get("/ml/report/latest/file?download=true")

    assert response.status_code == 404


def test_active_training_report_can_be_downloaded(
    client,
    db_session,
    tmp_path,
) -> None:
    report_path = tmp_path / "active-training-report.json"
    report_path.write_text(json.dumps({"candidates": []}), encoding="utf-8")
    artifact_path = tmp_path / "active.joblib"
    artifact_path.write_bytes(b"artifact-for-registry-test")
    job = MlTrainingJob(
        id="report-job",
        status="completed",
        execution_slot=None,
        requested_variants=[],
        result={},
        report_path=str(report_path),
    )
    db_session.add(job)
    db_session.commit()
    _register_active_model(
        db_session,
        artifact_path,
        model_id="report-model",
        job_id=job.id,
    )

    response = client.get("/ml/report/latest/file?download=true")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.json() == {"candidates": []}


def test_retrain_status_defaults_to_idle(client) -> None:
    response = client.get("/ml/retrain/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert body["message"] == "No training job exists."
    assert body["finished_at"] is None


def test_retrain_does_not_schedule_second_job_while_running(
    client,
    db_session,
    monkeypatch,
) -> None:
    db_session.add(MlTrainingJob(
        id="running-job",
        status="running",
        message="Retrain started in background.",
        execution_slot=1,
        requested_variants=[],
        result={},
    ))
    db_session.commit()
    monkeypatch.setattr(
        ml_router,
        "readiness_summary",
        lambda _session: {"training_ready": True},
    )

    response = client.post("/ml/retrain")

    assert response.status_code == 409
    body = response.json()
    assert "already queued or running" in body["detail"]


def test_ml_status_recommends_retraining_after_label_growth(
    client,
    monkeypatch,
    tmp_path,
    db_session,
) -> None:
    model_path = tmp_path / "growth-model.joblib"
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="baseline",
        pipeline=_FakePipeline(),
        model_version_id="growth-model",
        report={
            "labels": ["food"],
            "n_total_labelled": 1,
            "n_classes": 1,
            "models": {},
        },
    )
    joblib.dump(artifact, model_path)
    _register_active_model(
        db_session,
        model_path,
        model_id="growth-model",
        estimator="logreg",
    )
    _tx(db_session, dedup_hash="growth-1", category="food")
    _tx(db_session, dedup_hash="growth-2", category="transport")

    response = client.get("/ml/status")

    assert response.status_code == 200
    signal = response.json()["retrain_signal"]
    assert signal["retrain_recommended"] is True
    assert "label_growth_since_training" in signal["reason_codes"]
    assert signal["new_labels_since_training"] == 1


def test_ml_status_ignores_unregistered_artifact(client, monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "unregistered.joblib"
    joblib.dump(
        {
            "estimator": "linear_svc",
            "feature_set": "baseline",
            "pipeline": _FakePipeline(),
            "report": {
                "labels": ["food", "transport"],
                "n_total_labelled": 2,
                "n_classes": 2,
            },
        },
        model_path,
    )
    response = client.get("/ml/status")

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is False
    assert body["estimator"] is None
    assert body["compatibility_warnings"] == []


def test_ml_readiness_uses_confirmed_expense_labels(client, db_session) -> None:
    _tx(db_session, category="food", dedup_hash="ml-food")
    _tx(db_session, category="shopping", merchant="Allegro", dedup_hash="ml-shopping")
    _tx(
        db_session,
        amount=Decimal("5000"),
        direction="credit",
        category=None,
        transaction_type="income",
        merchant="ACME",
        title="Wynagrodzenie",
        dedup_hash="ml-income",
    )

    response = client.get("/ml/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["total_labelled"] == 2
    assert body["category_counts"]["food"] == 1
    assert body["category_counts"]["shopping"] == 1
    assert body["category_predicted_is_ground_truth"] is False


def test_ml_dashboard_ignores_stale_reports_without_registered_models(
    client, monkeypatch, tmp_path
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)

    def model_report(macro: float, weighted: float) -> dict:
        return {
            "macro_f1": macro,
            "weighted_f1": weighted,
            "confidence_curve": [
                {
                    "threshold": 0.55,
                    "coverage": 0.62,
                    "accuracy_on_covered": 0.84,
                    "covered": 42,
                }
            ],
            "confidence_note": "test confidence note",
            "skipped": False,
        }

    report = {
        "feature_variants": {
            "baseline": {
                "models": {
                    "linear_svc": model_report(0.61, 0.66),
                    "linear_svc_calibrated": model_report(0.60, 0.65),
                }
            },
            "feature_v2": {
                "models": {
                    "linear_svc": model_report(0.72, 0.76),
                    "linear_svc_calibrated": model_report(0.71, 0.75),
                    "dummy_most_frequent": model_report(0.10, 0.12),
                }
            },
        },
        "feature_decision": {
            "recommended_feature_set": "feature_v2",
            "reason": "feature_v2 improves macro-F1 without hurting threshold accuracy.",
        },
        "validation_slices": {
            "time_holdout": {
                "models": {
                    "linear_svc": {"macro_f1": 0.70, "skipped": False},
                    "linear_svc_calibrated": {"macro_f1": 0.69, "skipped": False},
                }
            },
            "merchant_group_holdout": {
                "models": {
                    "linear_svc": {"macro_f1": 0.68, "skipped": False},
                    "linear_svc_calibrated": {"macro_f1": 0.67, "skipped": False},
                }
            },
        },
        "confidence_policy": {"default_threshold": 0.55},
    }
    (reports_dir / "classification_20260101_120000.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    response = client.get("/ml/dashboard")

    assert response.status_code == 200
    body = response.json()
    recommendation = body["recommendation"]
    assert recommendation["estimator"] is None
    assert recommendation["feature_set"] is None
    assert recommendation["reason_code"] == "no_promotable_candidate"
    assert recommendation["based_on_report"] is False
    assert "train_recommended" in recommendation["action_codes"]
    assert body["status"]["exists"] is False
    assert body["status"]["report_path"] is None
    assert body["latest_report"]["path"] is None
    assert body["validation_slices"] == {}
    assert body["confidence_policy"] == {}
    assert body["feedback_quality"]["total_events"] == 0
    assert body["model_comparison"] == []


def test_ml_feedback_endpoint_records_event(client, db_session) -> None:
    tx = _tx(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.42,
        dedup_hash="ml-feedback-tx",
    )

    response = client.post(
        "/ml/feedback",
        json={
            "event_type": "reject_suggestion",
            "transaction_id": tx.id,
            "predicted_category": "food",
            "confidence": 0.42,
            "source": "model",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recorded"
    assert body["id"] is not None

    dashboard = client.get("/ml/dashboard").json()
    assert dashboard["feedback_quality"]["rejected_suggestions"] == 1
    assert dashboard["confusion_hotspots"][0]["predicted_category"] == "food"


def test_review_queue_prioritizes_high_value_uncertain_rows(client, db_session) -> None:
    high = _tx(
        db_session,
        dedup_hash="queue-high",
        category=None,
        amount=Decimal("-500.00"),
        merchant="Big Shop",
        category_predicted="other",
        category_confidence=0.95,
        raw_category="food",
    )
    _tx(
        db_session,
        dedup_hash="queue-low",
        category=None,
        amount=Decimal("-5.00"),
        merchant="Small Shop",
        category_predicted="food",
        category_confidence=0.80,
    )

    response = client.get("/ml/review-queue?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["transaction_id"] == high.id
    assert body[0]["priority_score"] > body[1]["priority_score"]
    assert body[0]["priority_components"]["other_risk"] > 0
    assert "bank_model_conflict" in body[0]["reason_codes"]


def test_feedback_report_returns_merchant_and_category_breakdowns(
    client,
    db_session,
) -> None:
    tx = _tx(
        db_session,
        dedup_hash="feedback-report",
        merchant="Lidl",
        category=None,
        category_predicted="food",
        category_confidence=0.44,
    )
    db_session.add(
        MlFeedbackEvent(
            transaction_id=tx.id,
            entity_type="transaction",
            entity_key=str(tx.id),
            event_type="manual_category",
            predicted_category="food",
            final_category="transport",
            confidence=0.44,
            source="model",
        )
    )
    db_session.commit()

    response = client.get("/ml/feedback-report")

    assert response.status_code == 200
    body = response.json()
    assert body["feedback_coverage"] is None
    assert body["coverage_basis"] == "not_tracked_per_event"
    assert body["top_corrected_merchants"][0]["merchant"] == "Lidl"
    assert body["category_corrections"][0]["predicted_category"] == "food"
