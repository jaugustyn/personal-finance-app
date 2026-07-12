from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from finance.domain.models import (
    MlEvaluationMember,
    MlEvaluationSet,
    MlFeedbackEvent,
    Transaction,
)
from finance.transactions.category_assignment import CategoryAssignmentService
from finance.transactions.suggestions import SuggestionAcceptanceService
from finance.transactions.type_decision import (
    TransactionTypeDecision,
    direction_matches,
    effective_transaction_type,
)
from finance.transactions.type_service import (
    TransactionTypeDirectionMismatch,
    TransactionTypeService,
)


def _tx(session, **overrides) -> Transaction:
    tx = Transaction(
        booking_date=date(2026, 4, 15),
        amount=Decimal("-50"),
        currency="PLN",
        direction="debit",
        merchant="Shop",
        title="Title",
        category=None,
        source="pekao",
        dedup_hash=f"use-case-{len(session.new)}-{overrides.get('dedup_hash', '')}",
    )
    for key, value in overrides.items():
        setattr(tx, key, value)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_category_assignment_service_records_manual_feedback(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="manual-category",
        category_predicted="shopping",
        category_confidence=0.42,
    )

    updated = CategoryAssignmentService(db_session).update_category(tx.id, "food")

    assert updated is not None
    assert updated.category == "food"
    event = (
        db_session.query(MlFeedbackEvent)
        .filter(MlFeedbackEvent.event_type == "manual_category")
        .one()
    )
    assert event.event_type == "manual_category"
    assert event.final_category == "food"


def test_transaction_type_service_clears_category_for_non_candidate(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="type-clear",
        category="food",
        category_source="manual",
        category_predicted="shopping",
        category_confidence=0.91,
    )
    evaluation_set = MlEvaluationSet(
        id="type-change-set",
        status="active",
        ontology_version="category_v1",
        dataset_fingerprint="snapshot",
        config={},
    )
    db_session.add(evaluation_set)
    db_session.add(
        MlEvaluationMember(
            evaluation_set_id=evaluation_set.id,
            transaction_id=tx.id,
            split="time",
            category="food",
            booking_date=tx.booking_date,
            merchant_hash="0" * 64,
        )
    )
    db_session.commit()

    updated = TransactionTypeService(db_session).update_transaction_type(
        tx.id, "other"
    )

    assert updated is not None
    assert updated.transaction_type == "other"
    assert updated.category is None
    assert updated.category_predicted is None
    db_session.refresh(evaluation_set)
    assert evaluation_set.status == "invalidated"
    event = (
        db_session.query(MlFeedbackEvent)
        .filter(MlFeedbackEvent.event_type == "manual_clear")
        .one()
    )
    assert event.event_type == "manual_clear"
    assert event.previous_category == "food"


def test_manual_type_requires_explicit_direction_mismatch_override(db_session) -> None:
    tx = _tx(db_session, dedup_hash="direction-warning")
    service = TransactionTypeService(db_session)

    with pytest.raises(TransactionTypeDirectionMismatch):
        service.apply_manual_type(tx, "salary")

    service.apply_manual_type(tx, "salary", allow_direction_mismatch=True)
    db_session.commit()
    assert tx.transaction_type == "salary"
    assert tx.transaction_type_confirmation_method == "manual"


def test_confirmed_type_is_not_overwritten_by_automatic_decision(db_session) -> None:
    tx = _tx(db_session, dedup_hash="protected-manual")
    service = TransactionTypeService(db_session)
    service.apply_manual_type(tx, "expense")

    changed = service.apply_decision(
        tx,
        TransactionTypeDecision(
            value="asset_allocation",
            mode="suggest_only",
            source="model",
            origin_ref="type_model_version:test",
            confidence=0.95,
        ),
    )

    assert changed is False
    assert tx.transaction_type == "expense"
    assert tx.transaction_type_predicted is None


def test_type_suggestion_does_not_change_effective_type_or_clear_category(
    db_session,
) -> None:
    tx = _tx(
        db_session,
        dedup_hash="suggestion-is-not-fact",
        category="food",
        category_source="manual",
        category_confirmation_method="manual",
        transaction_type=None,
    )

    changed = TransactionTypeService(db_session).apply_decision(
        tx,
        TransactionTypeDecision(
            value="asset_allocation",
            mode="suggest_only",
            source="rule",
            origin_ref="type_rule:v2:test",
        ),
    )

    assert changed is True
    assert tx.transaction_type_predicted == "asset_allocation"
    assert effective_transaction_type(tx) == "expense"
    assert tx.category == "food"


def test_accept_type_suggestion_creates_gold_label_with_provenance(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="accept-type",
        transaction_type_predicted="asset_allocation",
        transaction_type_predicted_source="model",
        transaction_type_predicted_ref="type_model_version:test",
        transaction_type_confidence=0.93,
    )

    updated = TransactionTypeService(db_session).accept_suggestion(tx.id)

    assert updated is not None
    assert updated.transaction_type == "asset_allocation"
    assert updated.transaction_type_confirmation_method == "accepted_suggestion"
    assert updated.transaction_type_source == "model"
    assert updated.transaction_type_origin_ref == "type_model_version:test"
    assert updated.transaction_type_predicted is None


def test_accept_active_provisional_type_creates_gold_label(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="accept-provisional-type",
        transaction_type="cash_withdrawal",
        transaction_type_source="bank",
        transaction_type_origin_ref="bank_type:pekao:v1:wyplata gotowki",
    )

    updated = TransactionTypeService(db_session).accept_suggestion(tx.id)

    assert updated is not None
    assert updated.transaction_type == "cash_withdrawal"
    assert updated.transaction_type_confirmation_method == "accepted_suggestion"
    assert updated.transaction_type_confirmed_at is not None
    assert updated.transaction_type_source == "bank"
    assert (
        updated.transaction_type_origin_ref
        == "bank_type:pekao:v1:wyplata gotowki"
    )


@pytest.mark.parametrize(
    ("transaction_type", "matching", "mismatching"),
    [
        ("expense", "debit", "credit"),
        ("salary", "credit", "debit"),
        ("income", "credit", "debit"),
        ("refund", "credit", "debit"),
        ("cash_withdrawal", "debit", "credit"),
        ("debt_payment", "debit", "credit"),
        ("asset_allocation", "debit", "credit"),
    ],
)
def test_transaction_type_expected_directions(
    transaction_type: str,
    matching: str,
    mismatching: str,
) -> None:
    assert direction_matches(transaction_type, matching)
    assert not direction_matches(transaction_type, mismatching)


@pytest.mark.parametrize("transaction_type", ["own_transfer", "other"])
@pytest.mark.parametrize("direction", ["debit", "credit"])
def test_bidirectional_transaction_types(
    transaction_type: str,
    direction: str,
) -> None:
    assert direction_matches(transaction_type, direction)


def test_suggestion_acceptance_service_accepts_policy_approved_prediction(
    db_session,
) -> None:
    tx = _tx(
        db_session,
        dedup_hash="accept-suggestion",
        category_predicted="transport",
        category_confidence=0.93,
        category_predicted_source="model",
    )

    affected = SuggestionAcceptanceService(db_session).accept_suggestions(
        ids=[tx.id],
        min_confidence=0.75,
    )

    assert affected == 1
    db_session.refresh(tx)
    assert tx.category == "transport"
    assert tx.category_source == "model"
