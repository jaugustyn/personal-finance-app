"""Regression tests for classifier artifact loading and prediction diagnostics."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy.orm import Session

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

    def predict(self, _x):
        return np.asarray([self.category])

    def predict_proba(self, _x):
        return np.asarray([[self.confidence, 1.0 - self.confidence]])


@pytest.fixture(autouse=True)
def _clear_classifier_caches():
    predict_mod.get_classifier.cache_clear()
    predict_mod.get_classifier_artifact.cache_clear()
    predict_mod.load_registered_artifact.cache_clear()
    yield
    predict_mod.get_classifier.cache_clear()
    predict_mod.get_classifier_artifact.cache_clear()
    predict_mod.load_registered_artifact.cache_clear()


def test_get_classifier_rejects_artifact_without_metadata(monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "classifier_latest.joblib"
    model_path.write_bytes(b"placeholder")
    pipe = _FakePipeline()

    predict_mod.get_classifier.cache_clear()
    monkeypatch.setattr(predict_mod, "LATEST_MODEL_PATH", model_path)
    monkeypatch.setattr(predict_mod.joblib, "load", lambda _path: {"pipeline": pipe})

    with pytest.raises(predict_mod.ClassifierNotAvailable, match="model_retrain_required"):
        predict_mod.get_classifier()


def test_get_classifier_accepts_locked_metadata(monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "classifier_latest.joblib"
    model_path.write_bytes(b"placeholder")
    pipe = _FakePipeline()
    artifact = build_model_artifact(
        estimator="logreg",
        feature_set="baseline",
        pipeline=pipe,
        report={},
    )
    monkeypatch.setattr(predict_mod, "LATEST_MODEL_PATH", model_path)
    monkeypatch.setattr(predict_mod.joblib, "load", lambda _path: artifact)

    assert predict_mod.get_classifier() is pipe


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
            confidence_policy={},
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


def test_predict_transaction_model_only(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.81))

    result = predict_mod.predict_transaction(
        "Lidl",
        "zakupy",
        Decimal("-25.50"),
        date(2026, 1, 10),
        policy=DEFAULT_POLICY,
    )

    assert result.category == "food"
    assert result.model_category == "food"
    assert result.confidence == 0.81
    assert result.source == "model"
    assert result.fallback_used is False
    assert result.recommended_action == "accept_candidate"
    assert result.classification_decision.action == "accept"
    assert result.top_predictions[0]["category"] == "food"
    assert result.top_predictions[0]["confidence"] == 0.81


def test_predict_transaction_marks_non_category_candidate(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.81))

    result = predict_mod.predict_transaction(
        "ACME",
        "Wynagrodzenie",
        Decimal("5000.00"),
        date(2026, 1, 10),
        transaction_type="income",
        policy=DEFAULT_POLICY,
    )

    assert result.recommended_action == "not_category_candidate"
    assert result.classification_decision.action == "not_applicable"


def test_predict_transaction_infers_credit_as_non_category_candidate(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.81))

    result = predict_mod.predict_transaction(
        "ACME",
        "Zwrot środków",
        Decimal("50.00"),
        date(2026, 1, 10),
        policy=DEFAULT_POLICY,
    )

    assert result.recommended_action == "not_category_candidate"
    assert result.classification_decision.action == "not_applicable"


def test_prediction_features_include_feature_v2_columns() -> None:
    row = predict_mod._row_to_features(
        "IKEA Kraków",
        "zakupy",
        Decimal("-120.00"),
        date(2026, 1, 10),
        source="pekao",
        transaction_type="expense",
    )

    assert row.iloc[0]["merchant_norm"]
    assert row.iloc[0]["amount_bucket"] == "medium"
    assert row.iloc[0]["month"] == 1
    assert row.iloc[0]["source"] == "pekao"


def test_predict_transaction_uses_valid_llm_fallback(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
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
        threshold=0.55,
        use_llm_fallback=True,
        policy=DEFAULT_POLICY,
    )

    assert result.category == "transport"
    assert result.model_category == "food"
    assert result.source == "llm"
    assert result.confidence is None
    assert result.model_confidence == 0.51
    assert result.fallback_used is True


def test_predict_transaction_rejects_invalid_llm_fallback(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(
        predict_mod,
        "get_settings",
        lambda: SimpleNamespace(llm_fallback_enabled=True),
    )
    monkeypatch.setattr(
        predict_mod.llm_client,
        "chat",
        lambda **_kwargs: {"content": "not_a_category"},
    )

    result = predict_mod.predict_transaction(
        "Unknown",
        "payment",
        Decimal("-99.00"),
        date(2026, 1, 10),
        threshold=0.55,
        use_llm_fallback=True,
        policy=DEFAULT_POLICY,
    )

    assert result.category == "food"
    assert result.source == "model"
    assert result.fallback_used is False


def test_reclassify_unlabelled_stores_prediction_and_confidence(db_session, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.82))
    monkeypatch.setattr(
        predict_mod,
        "require_registered_active_artifact",
        lambda _session: {},
    )
    monkeypatch.setattr(
        predict_mod,
        "get_classifier_artifact",
        lambda: (_ for _ in ()).throw(predict_mod.ClassifierNotAvailable()),
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

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 1
    db_session.refresh(tx)
    assert tx.category_predicted == "food"
    assert tx.category_confidence == 0.82
    assert tx.category_predicted_source == "model"
    assert tx.category is None


def test_reclassify_unlabelled_keeps_p2p_as_expense_candidate(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.82))
    monkeypatch.setattr(
        predict_mod,
        "require_registered_active_artifact",
        lambda _session: {},
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-200.00"),
        currency="PLN",
        direction="debit",
        merchant="Jan Kowalski",
        title="Przelew za bilety",
        category=None,
        source="pekao",
        dedup_hash="pred-transfer",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 1
    db_session.refresh(tx)
    assert tx.transaction_type is None
    assert tx.category_predicted == "food"


def test_reclassify_unlabelled_skips_debt_payment_without_model(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        predict_mod,
        "get_classifier",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be loaded")),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-650.00"),
        currency="PLN",
        direction="debit",
        merchant="Alior Bank",
        title="Rata kredytu gotówkowego",
        category=None,
        category_predicted="other",
        transaction_type="debt_payment",
        source="pekao",
        dedup_hash="pred-debt",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 0
    db_session.refresh(tx)
    assert tx.transaction_type == "debt_payment"
    assert tx.category_predicted is None


def test_reclassify_unlabelled_skips_credit_income_without_model(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        predict_mod,
        "get_classifier",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be loaded")),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("1220.00"),
        currency="PLN",
        direction="credit",
        merchant="WYŻSZA SZKOŁA EKONOMII I INFORMATYK",
        title="Stypendium rektora student",
        category=None,
        source="pekao",
        dedup_hash="pred-income",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 0
    db_session.refresh(tx)
    assert tx.transaction_type is None
    assert tx.category is None
    assert tx.category_predicted is None


def test_reclassify_unlabelled_applies_source_shopping_category_without_model(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        predict_mod,
        "get_classifier",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be loaded")),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-120.00"),
        currency="PLN",
        direction="debit",
        merchant="Allegro",
        title="Płatność online Allegro",
        raw_category="shopping",
        category=None,
        source="generic",
        dedup_hash="pred-source-shopping",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 1
    db_session.refresh(tx)
    assert tx.category is None
    assert tx.category_predicted == "shopping"
    assert tx.category_confidence is None
    assert tx.category_predicted_source == "bank"


def test_reclassify_unlabelled_skips_rejected_suggestions(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.82))
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-42.00"),
        currency="PLN",
        direction="debit",
        merchant="Lidl",
        title="zakupy",
        category=None,
        category_suggestion_rejected=True,
        source="pekao",
        dedup_hash="pred-rejected",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 0
    db_session.refresh(tx)
    assert tx.category_predicted is None


def test_reclassify_unlabelled_uses_personal_rule_before_model(
    db_session: Session,
    monkeypatch,
) -> None:
    create_rule(db_session, pattern="Lidl", category="food", mode="suggest_only")
    monkeypatch.setattr(
        predict_mod,
        "get_classifier",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be loaded")),
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
        dedup_hash="pred-personal-rule",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 1
    db_session.refresh(tx)
    assert tx.category is None
    assert tx.category_predicted == "food"
    assert tx.category_confidence == 0.95
    assert tx.category_predicted_source == "rule"


def test_reclassify_unlabelled_auto_apply_personal_rule(
    db_session: Session,
    monkeypatch,
) -> None:
    create_rule(db_session, pattern="Rent", category="housing", mode="auto_apply")
    monkeypatch.setattr(
        predict_mod,
        "get_classifier",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be loaded")),
    )
    tx = Transaction(
        booking_date=date(2026, 1, 10),
        amount=Decimal("-1500.00"),
        currency="PLN",
        direction="debit",
        merchant="Rent Company",
        title="czynsz",
        category=None,
        source="pekao",
        dedup_hash="pred-personal-auto",
    )
    db_session.add(tx)
    db_session.commit()

    updated = predict_mod.reclassify_unlabelled(db_session)

    assert updated == 1
    db_session.refresh(tx)
    assert tx.category == "housing"
    assert tx.category_source == "rule"
    assert tx.category_confirmation_method == "personal_rule_auto"
    assert tx.category_confirmed_at is None
    assert tx.category_predicted is None
