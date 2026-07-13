"""Regression tests for registry-only classifier loading and prediction."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest

from finance.domain.models import MlModelVersion, Transaction
from finance.ml.classification import predict as predict_mod
from finance.ml.classification.artifacts import artifact_sha256, build_model_artifact
from finance.ml.classification.policy import DEFAULT_POLICY
from finance.profile.service import create_rule


class _FakePipeline:
    def __init__(self, *, category: str = "food", confidence: float = 0.8) -> None:
        self.category = category
        self.confidence = confidence
        self.classes_ = np.asarray(["food", "transport"])

    def predict(self, _frame):
        return np.asarray([self.category])

    def predict_proba(self, _frame):
        return np.asarray([[self.confidence, 1.0 - self.confidence]])


def _artifact(*, confidence: float = 0.8) -> dict:
    return {
        "pipeline": _FakePipeline(confidence=confidence),
        "model_version_id": "model-1",
        "confidence_policy": {
            "source": "fixed_runtime_threshold",
            "default_threshold": 0.55,
            "per_category": {},
            "allow_other_accept": False,
        },
    }


@pytest.fixture(autouse=True)
def _clear_classifier_cache():
    predict_mod.load_registered_artifact.cache_clear()
    yield
    predict_mod.load_registered_artifact.cache_clear()


def test_registered_artifact_is_loaded_from_db_path_and_checksum(
    db_session,
    tmp_path,
) -> None:
    model_path = tmp_path / "immutable-candidate.joblib"
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="baseline",
        pipeline=_FakePipeline(),
        report={},
        model_version_id="registered-model",
    )
    predict_mod.joblib.dump(artifact, model_path)
    db_session.add(
        MlModelVersion(
            id="registered-model",
            estimator="logreg",
            feature_set="baseline",
            status="active",
            artifact_path=str(model_path),
            artifact_sha256=artifact_sha256(model_path),
            dataset_fingerprint="fingerprint",
            metrics={},
            gates={"promotable": True},
            confidence_policy={"default_threshold": 0.55},
            promotable=True,
        )
    )
    db_session.commit()

    loaded = predict_mod.require_registered_active_artifact(db_session)
    assert loaded["model_version_id"] == "registered-model"

    model_path.write_bytes(b"damaged")
    predict_mod.load_registered_artifact.cache_clear()
    with pytest.raises(predict_mod.ClassifierNotAvailable, match="checksum"):
        predict_mod.require_registered_active_artifact(db_session)


def test_prediction_requires_registered_artifact() -> None:
    with pytest.raises(predict_mod.ClassifierNotAvailable, match="registered artifact"):
        predict_mod.predict_transaction(
            "Lidl",
            "zakupy",
            Decimal("-25.50"),
            date(2026, 1, 10),
        )


def test_predict_transaction_uses_fixed_artifact_policy() -> None:
    result = predict_mod.predict_transaction(
        "Lidl",
        "zakupy",
        Decimal("-25.50"),
        date(2026, 1, 10),
        policy=None,
        artifact=_artifact(confidence=0.81),
    )

    assert result.category == "food"
    assert result.confidence == 0.81
    assert result.threshold == 0.55
    assert result.classification_decision.action == "accept"
    assert result.top_predictions[0] == {"category": "food", "confidence": 0.81}


def test_predict_transaction_marks_non_category_candidate() -> None:
    result = predict_mod.predict_transaction(
        "ACME",
        "Wynagrodzenie",
        Decimal("5000.00"),
        date(2026, 1, 10),
        transaction_type="income",
        policy=DEFAULT_POLICY,
        artifact=_artifact(confidence=0.81),
    )

    assert result.recommended_action == "not_category_candidate"
    assert result.classification_decision.action == "not_applicable"


def test_baseline_prediction_features_do_not_build_feature_v2_columns() -> None:
    row = predict_mod._row_to_features(
        "IKEA Kraków",
        "zakupy",
        Decimal("-120.00"),
        date(2026, 1, 10),
        source="pekao",
        transaction_type="expense",
    )

    assert "merchant_norm" not in row
    assert row.iloc[0]["source"] == "pekao"
    assert row.iloc[0]["text"] == "IKEA Kraków zakupy"


def test_llm_result_has_no_confidence_and_preserves_model_confidence(monkeypatch) -> None:
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

    result = predict_mod.predict_transaction(
        "Orlen",
        "paliwo",
        Decimal("-250.00"),
        date(2026, 1, 10),
        use_llm_fallback=True,
        policy=DEFAULT_POLICY,
        artifact=_artifact(confidence=0.51),
    )

    assert result.category == "transport"
    assert result.confidence is None
    assert result.model_confidence == 0.51
    assert result.fallback_used is True


def test_reclassify_unlabelled_stores_registered_model_prediction(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        predict_mod,
        "require_registered_active_artifact",
        lambda _session: _artifact(confidence=0.82),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-42.00"),
        currency="PLN",
        direction="debit",
        merchant="Lidl",
        title="zakupy",
        category=None,
        source="pekao",
        dedup_hash="pred-1",
    )
    db_session.add(tx)
    db_session.commit()

    assert predict_mod.reclassify_unlabelled(db_session) == 1
    db_session.refresh(tx)
    assert tx.category_predicted == "food"
    assert tx.category_confidence == 0.82
    assert tx.category_predicted_ref == "model_version:model-1"


def test_non_expense_is_cleared_without_loading_model(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        predict_mod,
        "require_registered_active_artifact",
        lambda _session: (_ for _ in ()).throw(AssertionError("model should not load")),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-650.00"),
        currency="PLN",
        direction="debit",
        merchant="Bank",
        title="Rata kredytu",
        category_predicted="other",
        transaction_type="debt_payment",
        source="pekao",
        dedup_hash="pred-debt",
    )
    db_session.add(tx)
    db_session.commit()

    assert predict_mod.reclassify_unlabelled(db_session) == 0
    db_session.refresh(tx)
    assert tx.category_predicted is None


def test_personal_rule_runs_before_model(db_session, monkeypatch) -> None:
    create_rule(db_session, pattern="Lidl", category="food", mode="suggest_only")
    monkeypatch.setattr(
        predict_mod,
        "require_registered_active_artifact",
        lambda _session: (_ for _ in ()).throw(AssertionError("model should not load")),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-42.00"),
        currency="PLN",
        direction="debit",
        merchant="Lidl",
        title="zakupy",
        source="pekao",
        dedup_hash="pred-personal-rule",
    )
    db_session.add(tx)
    db_session.commit()

    assert predict_mod.reclassify_unlabelled(db_session) == 1
    db_session.refresh(tx)
    assert tx.category is None
    assert tx.category_predicted == "food"
    assert tx.category_predicted_source == "rule"
