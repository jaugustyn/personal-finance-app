"""Operational feedback metrics only cover transactions that still exist."""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from finance.domain.models import Transaction
from finance.ml.feedback import (
    EVENT_ACCEPT_SUGGESTION,
    FeedbackEventInput,
    feedback_quality,
    feedback_report,
    record_feedback_event,
)


def test_operational_feedback_excludes_events_without_live_transaction(
    db_session: Session,
) -> None:
    transaction = Transaction(
        booking_date=date(2026, 1, 1),
        amount=Decimal("-10.00"),
        currency="PLN",
        direction="debit",
        merchant="Shop",
        title="",
        source="unknown",
        dedup_hash="feedback-live-transaction",
        is_transfer=False,
    )
    db_session.add(transaction)
    db_session.flush()
    record_feedback_event(
        db_session,
        FeedbackEventInput(
            event_type=EVENT_ACCEPT_SUGGESTION,
            transaction_id=transaction.id,
            predicted_category="food",
        ),
    )
    record_feedback_event(
        db_session,
        FeedbackEventInput(
            event_type=EVENT_ACCEPT_SUGGESTION,
            transaction_id=None,
            entity_type="transaction",
            entity_key="deleted",
            predicted_category="food",
        ),
    )
    db_session.commit()

    quality = feedback_quality(db_session)
    report = feedback_report(db_session)

    assert quality["total_events"] == 1
    assert quality["accepted_suggestions"] == 1
    assert report["quality"]["total_events"] == 1
