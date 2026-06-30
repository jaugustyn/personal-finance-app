from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.models import MlFeedbackEvent, Transaction
from finance.transactions.category_assignment import CategoryAssignmentService
from finance.transactions.suggestions import SuggestionAcceptanceService
from finance.transactions.type_service import TransactionTypeService


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
    event = db_session.query(MlFeedbackEvent).one()
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

    updated = TransactionTypeService(db_session).update_transaction_type(
        tx.id, "person_transfer"
    )

    assert updated is not None
    assert updated.transaction_type == "person_transfer"
    assert updated.category is None
    assert updated.category_predicted is None


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
