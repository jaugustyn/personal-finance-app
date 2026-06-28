"""API tests for subscription feedback and hiding."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.models import MerchantAlias, Transaction
from finance.transactions.merchants import merchant_identity


def _subscription_tx(month: int, merchant: str = "Spotify") -> Transaction:
    return Transaction(
        booking_date=date(2026, month, 5),
        amount=Decimal("-29.99"),
        currency="PLN",
        amount_base=Decimal("-29.99"),
        base_currency="PLN",
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


def test_subscription_feedback_hides_product_level_merchant(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month, merchant="Spotify Premium"))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert before.status_code == 200
    assert any(row["merchant"] == "Spotify Premium" for row in before.json())

    feedback = client.post(
        "/subscriptions/feedback",
        json={"merchant": "Spotify Premium", "action": "hide"},
    )
    assert feedback.status_code == 200

    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert after.status_code == 200
    assert all(row["merchant"] != "Spotify Premium" for row in after.json())


def test_subscriptions_use_merchant_aliases_for_grouping(client, db_session) -> None:
    db_session.add_all(
        [
            MerchantAlias(
                alias_key="netflix com amsterdam",
                alias_label="NETFLIX.COM AMSTERDAM",
                canonical_key="netflix",
                canonical_label="Netflix",
            ),
            MerchantAlias(
                alias_key="netflix payu",
                alias_label="NETFLIX PAYU",
                canonical_key="netflix",
                canonical_label="Netflix",
            ),
        ]
    )
    for idx, merchant in enumerate(
        [
            "NETFLIX.COM AMSTERDAM",
            "NETFLIX PAYU",
            "NETFLIX.COM AMSTERDAM",
            "NETFLIX PAYU",
        ],
        start=1,
    ):
        db_session.add(
            Transaction(
                booking_date=date(2026, idx, 10),
                amount=Decimal("-67.99"),
                currency="PLN",
                direction="debit",
                merchant=merchant,
                title="",
                category="subscriptions",
                source="pekao",
                dedup_hash=f"sub-netflix-alias-{idx}",
                is_transfer=False,
                transaction_type="purchase",
            )
        )
    db_session.commit()

    response = client.get("/subscriptions", params={"min_confidence": 0.0})

    assert response.status_code == 200
    rows = response.json()
    netflix_rows = [row for row in rows if row["merchant"] == "Netflix"]
    assert len(netflix_rows) == 1
    assert netflix_rows[0]["occurrences"] == 4
    assert netflix_rows[0]["estimated_monthly_cost"] == 67.99


def test_manual_subscription_category_creates_confirmed_row(client, db_session) -> None:
    db_session.add(
        Transaction(
            booking_date=date(2026, 6, 10),
            amount=Decimal("-49.99"),
            currency="PLN",
            amount_base=Decimal("-49.99"),
            base_currency="PLN",
            direction="debit",
            merchant="Netflix",
            title="manual subscription",
            category="subscriptions",
            category_source="manual",
            source="pekao",
            dedup_hash="manual-netflix-sub",
            is_transfer=False,
            transaction_type="purchase",
        )
    )
    db_session.commit()

    response = client.get("/subscriptions", params={"min_confidence": 1.0})

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["display_name"] == "Netflix"
    assert rows[0]["source"] == "category"
    assert rows[0]["is_confirmed"] is True
    assert rows[0]["status"] == "needs_review"


def test_confirmed_subscription_is_not_hidden_by_min_confidence(client, db_session) -> None:
    db_session.add_all(
        [
            Transaction(
                booking_date=date(2026, 1, 1),
                amount=Decimal("-20.00"),
                currency="PLN",
                amount_base=Decimal("-20.00"),
                base_currency="PLN",
                direction="debit",
                merchant="Low Confidence App",
                title="",
                category=None,
                source="pekao",
                dedup_hash="low-sub-1",
                is_transfer=False,
                transaction_type="purchase",
            ),
            Transaction(
                booking_date=date(2026, 2, 1),
                amount=Decimal("-20.00"),
                currency="PLN",
                amount_base=Decimal("-20.00"),
                base_currency="PLN",
                direction="debit",
                merchant="Low Confidence App",
                title="",
                category=None,
                source="pekao",
                dedup_hash="low-sub-2",
                is_transfer=False,
                transaction_type="purchase",
            ),
        ]
    )
    db_session.commit()

    subscription_key = f"{merchant_identity('Low Confidence App').canonical_key}|pln"

    before = client.get("/subscriptions", params={"min_confidence": 0.99})
    assert before.status_code == 200
    assert before.json() == []

    preference = client.post(
        "/subscriptions/preference",
        json={
            "subscription_key": subscription_key,
            "action": "confirm",
            "display_name": "Low Confidence App",
        },
    )
    assert preference.status_code == 200

    after = client.get("/subscriptions", params={"min_confidence": 0.99})
    assert after.status_code == 200
    assert [row["display_name"] for row in after.json()] == ["Low Confidence App"]
    assert after.json()[0]["is_confirmed"] is True


def test_subscription_preference_ignores_row(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month, merchant="Ignore Me"))
    db_session.commit()

    response = client.post(
        "/subscriptions/preference",
        json={"subscription_key": "ignore me|pln", "action": "ignore"},
    )
    assert response.status_code == 200

    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert after.status_code == 200
    assert all(row["display_name"] != "Ignore Me" for row in after.json())


def test_subscription_price_increase_status(client, db_session) -> None:
    for month, amount in [(3, "-49.99"), (4, "-49.99"), (5, "-60.00"), (6, "-60.00")]:
        db_session.add(
            Transaction(
                booking_date=date(2026, month, 12),
                amount=Decimal(amount),
                currency="PLN",
                amount_base=Decimal(amount),
                base_currency="PLN",
                direction="debit",
                merchant="Streaming Plus",
                title="",
                category="subscriptions",
                source="pekao",
                dedup_hash=f"streaming-plus-{month}",
                is_transfer=False,
                transaction_type="purchase",
            )
        )
    db_session.commit()

    response = client.get("/subscriptions", params={"min_confidence": 0.0})

    assert response.status_code == 200
    row = next(row for row in response.json() if row["display_name"] == "Streaming Plus")
    assert row["status"] == "price_increased"
    assert row["current_amount"] == 60.0
    assert row["price_change_pct"] is not None


def test_subscription_overview_returns_kpis(client, db_session) -> None:
    for month in range(3, 7):
        db_session.add(_subscription_tx(month))
    db_session.commit()

    response = client.get("/subscriptions/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["monthly_total"] == 29.99
    assert data["yearly_total"] == 359.88
    assert data["base_currency"] == "PLN"
