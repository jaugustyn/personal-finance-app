"""Regression tests for classifier artifact loading and prediction diagnostics."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
from sqlalchemy.orm import Session

from finance.domain.models import Transaction
from finance.ml.classification import predict as predict_mod
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


def test_get_classifier_accepts_metadata_dict(monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "classifier_latest.joblib"
    model_path.write_bytes(b"placeholder")
    pipe = _FakePipeline()

    predict_mod.get_classifier.cache_clear()
    monkeypatch.setattr(predict_mod, "LATEST_MODEL_PATH", model_path)
    monkeypatch.setattr(predict_mod.joblib, "load", lambda _path: {"pipeline": pipe})

    assert predict_mod.get_classifier() is pipe
    predict_mod.get_classifier.cache_clear()


def test_predict_transaction_model_only(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.81))

    result = predict_mod.predict_transaction(
        "Lidl",
        "zakupy",
        Decimal("-25.50"),
        date(2026, 1, 10),
    )

    assert result.category == "food"
    assert result.model_category == "food"
    assert result.confidence == 0.81
    assert result.source == "model"
    assert result.fallback_used is False
    assert result.recommended_action == "accept_candidate"
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
    )

    assert result.recommended_action == "not_category_candidate"


def test_prediction_features_include_feature_v2_columns() -> None:
    row = predict_mod._row_to_features(
        "IKEA Kraków",
        "zakupy",
        Decimal("-120.00"),
        date(2026, 1, 10),
        source="pekao",
        transaction_type="purchase",
    )

    assert row.iloc[0]["merchant_norm"]
    assert row.iloc[0]["amount_bucket"] == "medium"
    assert row.iloc[0]["month"] == 1
    assert row.iloc[0]["source"] == "pekao"


def test_predict_transaction_uses_valid_llm_fallback(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
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
    )

    assert result.category == "transport"
    assert result.model_category == "food"
    assert result.source == "llm_fallback"
    assert result.fallback_used is True


def test_predict_transaction_rejects_invalid_llm_fallback(monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.51))
    monkeypatch.setattr(predict_mod.llm_client, "is_available", lambda: True)
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
    )

    assert result.category == "food"
    assert result.source == "model"
    assert result.fallback_used is False


def test_reclassify_unlabelled_stores_prediction_and_confidence(db_session, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.82))
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


def test_reclassify_unlabelled_skips_person_transfers(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(predict_mod, "get_classifier", lambda: _FakePipeline(confidence=0.82))
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

    assert updated == 0
    db_session.refresh(tx)
    assert tx.transaction_type == "person_transfer"
    assert tx.category_predicted is None


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
    assert tx.transaction_type == "income"
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
    assert tx.category == "shopping"
    assert tx.category_source == "bank"
    assert tx.category_predicted is None


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
    assert tx.category_predicted is None
