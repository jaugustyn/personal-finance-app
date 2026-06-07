"""API tests for subscription feedback and hiding."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.models import Transaction


def _subscription_tx(month: int, merchant: str = "Spotify") -> Transaction:
    return Transaction(
        booking_date=date(2026, month, 5),
        amount=Decimal("-29.99"),
        currency="PLN",
        direction="debit",
        merchant=merchant,
        title="abonament",
        category="subscriptions",
        source="pekao",
        dedup_hash=f"sub-{merchant}-{month}",
        is_transfer=False,
        transaction_type="purchase",
    )


def test_subscription_feedback_hides_merchant(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})

    assert before.status_code == 200
    assert any(row["merchant"] == "Spotify" for row in before.json())

    feedback = client.post(
        "/subscriptions/feedback",
        json={"merchant": "Spotify", "action": "hide"},
    )

    assert feedback.status_code == 200
    assert feedback.json()["status"] == "recorded"
    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert after.status_code == 200
    assert all(row["merchant"] != "Spotify" for row in after.json())

    summary = client.get("/transactions/review-summary").json()
    assert summary["subscription_feedback"]["hidden"] == 1
