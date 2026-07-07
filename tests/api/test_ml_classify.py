"""API tests for classifier diagnostics and optional LLM fallback."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from apps.api.routers import ml as ml_router
from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.classification import predict as predict_mod
from finance.ml.classification.artifacts import build_model_artifact


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
    monkeypatch.setattr(ml_router, "REPORTS_DIR", reports_dir)
    ml_router._set_retrain_state(status="idle")
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
        transaction_type="purchase",
        is_transfer=False,
    )
    for key, value in overrides.items():
        setattr(tx, key, value)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_classify_returns_model_diagnostics(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.83))

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
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
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
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.91))

    response = client.post(
        "/ml/classify",
        json=_payload(transaction_type="income"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "not_category_candidate"
    assert body["classification_decision"]["action"] == "not_applicable"


def test_classify_infers_credit_amount_as_non_category_candidate(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.91))

    response = client.post(
        "/ml/classify",
        json=_payload(amount="50.00"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "not_category_candidate"
    assert body["classification_decision"]["action"] == "not_applicable"


def test_classify_uses_category_threshold_from_latest_report(
    client,
    monkeypatch,
    _isolated_reports_dir,
) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.83))
    report = {
        "confidence_policy": {
            "default_threshold": 0.55,
            "per_category": {"food": {"threshold": 0.90}},
        }
    }
    (_isolated_reports_dir / "classification_20260101.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    response = client.post("/ml/classify", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "review"
    assert body["threshold_used"] == 0.90
    assert body["classification_decision"]["action"] == "review"
    assert body["classification_decision"]["threshold_used"] == 0.90


def test_classify_uses_valid_llm_fallback_when_enabled(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
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
    assert body["source"] == "llm_fallback"
    assert body["fallback_used"] is True


def test_classify_rejects_invalid_llm_category(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
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
    monkeypatch.setattr(ml_router, "MODEL_PATH", tmp_path / "missing.joblib")
    monkeypatch.setattr(ml_router, "REPORTS_DIR", tmp_path / "reports")

    response = client.get("/ml/status")

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is False
    assert "shopping" in body["missing_categories"]
    assert body["classes"] == []
    assert body["compatibility_warnings"] == []


def test_ml_status_reports_artifact_metadata(client, monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "classifier_latest.joblib"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    artifact = build_model_artifact(
        estimator="linear_svc",
        feature_set="baseline",
        pipeline=_FakePipeline(),
        report={
            "labels": ["food", "transport"],
            "n_total_labelled": 2,
            "n_classes": 2,
            "models": {
                "linear_svc": {
                    "macro_f1": 0.8,
                    "weighted_f1": 0.82,
                    "confidence_curve": [],
                    "skipped": False,
                }
            },
        },
    )
    ml_router.joblib.dump(artifact, model_path)
    monkeypatch.setattr(ml_router, "MODEL_PATH", model_path)
    monkeypatch.setattr(ml_router, "REPORTS_DIR", reports_dir)

    response = client.get("/ml/status")

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is True
    assert body["estimator"] == "linear_svc"
    assert body["artifact_metadata"]["artifact_schema_version"] == "1.0"
    assert "sklearn" in body["artifact_metadata"]["runtime_versions"]
    assert body["compatibility_warnings"] == []
    assert body["retrain_signal"]["retrain_recommended"] is False


def test_latest_report_file_can_be_downloaded(client, _isolated_reports_dir) -> None:
    report_path = _isolated_reports_dir / "classification_20260101_120000.json"
    report_path.write_text(json.dumps({"models": {}, "labels": ["food"]}), encoding="utf-8")

    response = client.get("/ml/report/latest/file?download=true")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    assert report_path.name in response.headers["content-disposition"]
    assert response.json() == {"models": {}, "labels": ["food"]}


def test_retrain_status_defaults_to_idle(client) -> None:
    response = client.get("/ml/retrain/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert body["message"] is None
    assert body["finished_at"] is None


def test_retrain_does_not_schedule_second_job_while_running(client) -> None:
    ml_router._set_retrain_state(
        status="running",
        message="Retrain started in background.",
        estimator="linear_svc_calibrated",
        feature_set="feature_v2",
        started_at="2026-01-10T10:00:00+00:00",
        finished_at=None,
    )

    response = client.post("/ml/retrain")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "running"
    assert body["message"] == "Retrain is already running in background."


def test_ml_status_recommends_retraining_after_label_growth(
    client,
    monkeypatch,
    tmp_path,
    db_session,
) -> None:
    model_path = tmp_path / "classifier_latest.joblib"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    artifact = build_model_artifact(
        estimator="linear_svc",
        feature_set="baseline",
        pipeline=_FakePipeline(),
        report={
            "labels": ["food"],
            "n_total_labelled": 1,
            "n_classes": 1,
            "models": {},
        },
    )
    ml_router.joblib.dump(artifact, model_path)
    monkeypatch.setattr(ml_router, "MODEL_PATH", model_path)
    monkeypatch.setattr(ml_router, "REPORTS_DIR", reports_dir)
    _tx(db_session, dedup_hash="growth-1", category="food")
    _tx(db_session, dedup_hash="growth-2", category="transport")

    response = client.get("/ml/status")

    assert response.status_code == 200
    signal = response.json()["retrain_signal"]
    assert signal["retrain_recommended"] is True
    assert "label_growth_since_training" in signal["reason_codes"]
    assert signal["new_labels_since_training"] == 1


def test_ml_status_warns_for_artifact_without_metadata(client, monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "classifier_latest.joblib"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    ml_router.joblib.dump(
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
    monkeypatch.setattr(ml_router, "MODEL_PATH", model_path)
    monkeypatch.setattr(ml_router, "REPORTS_DIR", reports_dir)

    response = client.get("/ml/status")

    assert response.status_code == 200
    body = response.json()
    assert body["compatibility_warnings"] == ["missing_artifact_metadata"]


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


def test_ml_dashboard_compares_models_and_recommends_calibrated_variant(
    client, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(ml_router, "MODEL_PATH", tmp_path / "missing.joblib")
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ml_router, "REPORTS_DIR", reports_dir)

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
    assert recommendation["estimator"] == "linear_svc_calibrated"
    assert recommendation["feature_set"] == "feature_v2"
    assert recommendation["reason_code"] == "prefer_calibrated_close"
    assert recommendation["based_on_report"] is True
    assert "train_recommended" in recommendation["action_codes"]
    assert body["validation_slices"]["time_holdout"]
    assert body["confidence_policy"]["default_threshold"] == 0.55
    assert body["feedback_quality"]["total_events"] == 0

    rows = body["model_comparison"]
    recommended_rows = [row for row in rows if row["is_recommended"]]
    assert len(recommended_rows) == 1
    assert recommended_rows[0]["estimator"] == "linear_svc_calibrated"
    assert abs(recommended_rows[0]["stability_score"] - 0.68) < 1e-9
    assert rows[0]["estimator"] == "linear_svc"
    assert rows[0]["feature_set"] == "feature_v2"


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
