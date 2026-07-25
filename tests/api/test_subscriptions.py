"""API tests for subscription feedback and lifecycle data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.models import MerchantAlias, Transaction
from finance.ml.subscriptions import projection as subscription_projection
from finance.ml.subscriptions import service as subscription_service
from finance.ml.subscriptions.service import list_subscription_rows
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
        transaction_type="expense",
    )


def test_subscription_feedback_confirms_without_hiding_merchant(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})

    assert before.status_code == 200
    assert any(row["merchant"] == "Spotify" for row in before.json())

    feedback = client.post(
        "/subscriptions/feedback",
        json={"merchant": "Spotify", "action": "confirm"},
    )

    assert feedback.status_code == 200
    assert feedback.json()["status"] == "recorded"
    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert after.status_code == 200
    spotify = next(row for row in after.json() if row["merchant"] == "Spotify")
    assert spotify["is_confirmed"] is True

    summary = client.get("/transactions/review-summary").json()
    assert summary["subscription_feedback"]["confirmed"] == 1


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
                transaction_type="expense",
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
    assert len(netflix_rows[0]["transactions"]) == 4


def test_subscription_uses_title_when_merchant_is_generic(client, db_session) -> None:
    for idx, title in enumerate(
        [
            "CARD PAYMENT NETFLIX",
            "CARD PAYMENT NETFLIX.COM",
            "CARD PAYMENT NETFLIX",
            "CARD PAYMENT NETFLIX.COM",
        ],
        start=1,
    ):
        db_session.add(
            Transaction(
                booking_date=date(2026, idx, 12),
                amount=Decimal("-49.99"),
                currency="PLN",
                amount_base=Decimal("-49.99"),
                base_currency="PLN",
                direction="debit",
                merchant="CARD PAYMENT",
                title=title,
                category="subscriptions",
                source="pekao",
                dedup_hash=f"generic-netflix-{idx}",
                is_transfer=False,
                transaction_type="expense",
            )
        )
    db_session.commit()

    response = client.get("/subscriptions", params={"min_confidence": 0.0})

    assert response.status_code == 200
    rows = response.json()
    netflix_rows = [row for row in rows if "netflix" in row["display_name"].lower()]
    assert len(netflix_rows) == 1
    assert netflix_rows[0]["occurrences"] == 4


def test_subscription_feedback_can_confirm_exact_subscription_key(client, db_session) -> None:
    for idx, title in enumerate(
        [
            "CARD PAYMENT NETFLIX",
            "CARD PAYMENT NETFLIX.COM",
        ],
        start=1,
    ):
        db_session.add(
            Transaction(
                booking_date=date(2026, idx, 12),
                amount=Decimal("-49.99"),
                currency="PLN",
                amount_base=Decimal("-49.99"),
                base_currency="PLN",
                direction="debit",
                merchant="CARD PAYMENT",
                title=title,
                category="subscriptions",
                source="pekao",
                dedup_hash=f"generic-netflix-feedback-{idx}",
                is_transfer=False,
                transaction_type="expense",
            )
        )
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert before.status_code == 200
    row = next(item for item in before.json() if "netflix" in item["display_name"].lower())
    assert row["is_confirmed"] is False

    feedback = client.post(
        "/subscriptions/feedback",
        json={
            "merchant": row["display_name"],
            "subscription_key": row["merchant_key"],
            "action": "confirm",
        },
    )

    assert feedback.status_code == 200
    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    confirmed = next(item for item in after.json() if item["merchant_key"] == row["merchant_key"])
    assert confirmed["is_confirmed"] is True


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
            transaction_type="expense",
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
    assert rows[0]["user_decision"] == "confirmed"
    assert rows[0]["status"] == "needs_review"


def test_rejected_subscription_is_removed_from_list(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month, merchant="Reject Me"))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert before.status_code == 200
    row = next(item for item in before.json() if item["display_name"] == "Reject Me")

    rejected = client.post(
        "/subscriptions/preference",
        json={"subscription_key": row["merchant_key"], "action": "reject"},
    )

    assert rejected.status_code == 200
    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    assert after.status_code == 200
    assert all(item["merchant_key"] != row["merchant_key"] for item in after.json())

    rejected_rows = client.get(
        "/subscriptions",
        params={"min_confidence": 0.0, "include_rejected": True},
    )
    assert rejected_rows.status_code == 200
    rejected_row = next(
        item for item in rejected_rows.json() if item["merchant_key"] == row["merchant_key"]
    )
    assert rejected_row["user_decision"] == "rejected"
    assert rejected_row["is_confirmed"] is False


def test_restore_subscription_makes_rejected_row_visible_again(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month, merchant="Restore Me"))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})
    row = next(item for item in before.json() if item["display_name"] == "Restore Me")

    reject = client.post(
        "/subscriptions/preference",
        json={"subscription_key": row["merchant_key"], "action": "reject"},
    )
    assert reject.status_code == 200

    restore = client.post(
        "/subscriptions/preference",
        json={"subscription_key": row["merchant_key"], "action": "restore"},
    )
    assert restore.status_code == 200

    after = client.get("/subscriptions", params={"min_confidence": 0.0})
    restored = next(item for item in after.json() if item["merchant_key"] == row["merchant_key"])
    assert restored["user_decision"] == "suggested"
    assert restored["is_confirmed"] is False


def test_confirm_after_reject_returns_confirmed_subscription(client, db_session) -> None:
    for month in range(1, 5):
        db_session.add(_subscription_tx(month, merchant="Confirm After Reject"))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})
    row = next(item for item in before.json() if item["display_name"] == "Confirm After Reject")

    reject = client.post(
        "/subscriptions/preference",
        json={"subscription_key": row["merchant_key"], "action": "reject"},
    )
    assert reject.status_code == 200
    confirm = client.post(
        "/subscriptions/preference",
        json={
            "subscription_key": row["merchant_key"],
            "action": "confirm",
            "display_name": "Confirm After Reject",
        },
    )
    assert confirm.status_code == 200

    after = client.get("/subscriptions", params={"min_confidence": 0.99})
    confirmed = next(item for item in after.json() if item["merchant_key"] == row["merchant_key"])
    assert confirmed["user_decision"] == "confirmed"
    assert confirmed["is_confirmed"] is True


def test_subscription_overview_ignores_rejected_rows(client, db_session) -> None:
    for month in range(3, 7):
        db_session.add(_subscription_tx(month, merchant="Rejected KPI"))
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 0.0})
    row = next(item for item in before.json() if item["display_name"] == "Rejected KPI")
    reject = client.post(
        "/subscriptions/preference",
        json={"subscription_key": row["merchant_key"], "action": "reject"},
    )
    assert reject.status_code == 200

    overview = client.get("/subscriptions/overview")
    assert overview.status_code == 200
    assert overview.json()["monthly_total"] == 0
    assert overview.json()["next_30_days_count"] == 0


def test_reject_manual_category_hides_subscription_not_transaction_category(
    client,
    db_session,
) -> None:
    tx_ids: list[int] = []
    for month in range(1, 3):
        tx = Transaction(
            booking_date=date(2026, month, 10),
            amount=Decimal("-19.00"),
            currency="PLN",
            amount_base=Decimal("-19.00"),
            base_currency="PLN",
            direction="debit",
            merchant="Manual Reject",
            title="manual category",
            category="subscriptions",
            category_source="manual",
            source="pekao",
            dedup_hash=f"manual-reject-{month}",
            is_transfer=False,
            transaction_type="expense",
        )
        db_session.add(tx)
        db_session.flush()
        tx_ids.append(tx.id)
    db_session.commit()

    before = client.get("/subscriptions", params={"min_confidence": 1.0})
    row = next(item for item in before.json() if item["display_name"] == "Manual Reject")
    reject = client.post(
        "/subscriptions/preference",
        json={"subscription_key": row["merchant_key"], "action": "reject"},
    )
    assert reject.status_code == 200

    after = client.get("/subscriptions", params={"min_confidence": 1.0})
    assert all(item["merchant_key"] != row["merchant_key"] for item in after.json())
    stored = db_session.get(Transaction, tx_ids[0])
    assert stored is not None
    assert stored.category == "subscriptions"
    assert stored.category_source == "manual"


def test_stale_unknown_cadence_subscription_is_not_active(db_session) -> None:
    db_session.add_all(
        [
            Transaction(
                booking_date=date(2024, 1, 1),
                amount=Decimal("-99.00"),
                currency="PLN",
                amount_base=Decimal("-99.00"),
                base_currency="PLN",
                direction="debit",
                merchant="InterviewMe",
                title="old manual subscription",
                category="subscriptions",
                category_source="manual",
                source="pekao",
                dedup_hash="interviewme-old-1",
                is_transfer=False,
                transaction_type="expense",
            ),
            Transaction(
                booking_date=date(2024, 3, 11),
                amount=Decimal("-99.00"),
                currency="PLN",
                amount_base=Decimal("-99.00"),
                base_currency="PLN",
                direction="debit",
                merchant="InterviewMe",
                title="old manual subscription",
                category="subscriptions",
                category_source="manual",
                source="pekao",
                dedup_hash="interviewme-old-2",
                is_transfer=False,
                transaction_type="expense",
            ),
        ]
    )
    db_session.commit()

    rows = list_subscription_rows(db_session, as_of=date(2026, 6, 28))

    row = next(item for item in rows if item.display_name == "InterviewMe")
    assert row.cadence == "unknown"
    assert row.status == "probably_cancelled"


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
                transaction_type="expense",
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
                transaction_type="expense",
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


def test_subscription_price_increase_status(client, db_session, monkeypatch) -> None:
    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 7, 1)

    monkeypatch.setattr(subscription_service, "date", _FixedDate)
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
                transaction_type="expense",
            )
        )
    db_session.commit()

    response = client.get("/subscriptions", params={"min_confidence": 0.0})

    assert response.status_code == 200
    row = next(row for row in response.json() if row["display_name"] == "Streaming Plus")
    assert row["status"] == "price_increased"
    assert row["current_amount"] == 60.0
    assert row["price_change_pct"] is not None


def test_subscription_overview_returns_kpis(client, db_session, monkeypatch) -> None:
    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 7, 1)

    monkeypatch.setattr(subscription_service, "date", _FixedDate)
    for month in range(3, 7):
        db_session.add(_subscription_tx(month))
    db_session.commit()

    response = client.get("/subscriptions/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["monthly_total"] == 29.99
    assert data["yearly_total"] == 359.88
    assert data["base_currency"] == "PLN"


def test_subscription_overview_skips_unused_row_details(
    client,
    db_session,
    monkeypatch,
) -> None:
    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 7, 1)

    monkeypatch.setattr(subscription_service, "date", _FixedDate)
    for month in range(3, 7):
        db_session.add(_subscription_tx(month))
    db_session.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("overview should not build transaction details")

    monkeypatch.setattr(
        subscription_projection,
        "transaction_samples",
        fail_if_called,
    )
    monkeypatch.setattr(
        subscription_projection,
        "sample_evidence",
        fail_if_called,
    )

    response = client.get("/subscriptions/overview")

    assert response.status_code == 200
    assert response.json()["monthly_total"] == 29.99
