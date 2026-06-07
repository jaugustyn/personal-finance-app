"""API tests for classifier diagnostics and optional LLM fallback."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import numpy as np

from apps.api.routers import ml as ml_router
from finance.domain.models import Transaction
from finance.ml.classification import predict as predict_mod


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


def test_classify_marks_non_category_candidate(client, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.91))

    response = client.post(
        "/ml/classify",
        json=_payload(transaction_type="income"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_action"] == "not_category_candidate"


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
    reports_dir.mkdir()
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
