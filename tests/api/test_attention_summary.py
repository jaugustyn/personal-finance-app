from datetime import date
from decimal import Decimal

from finance import attention
from finance.domain.enums import TransactionDirection, TransactionType
from finance.domain.models import Transaction


def _transaction(*, dedup_hash: str, **values: object) -> Transaction:
    fields: dict[str, object] = {
        "booking_date": date(2026, 1, 1),
        "amount": Decimal("-10.00"),
        "currency": "PLN",
        "direction": TransactionDirection.DEBIT.value,
        "merchant": "Test merchant",
        "title": "",
        "source": "unknown",
        "dedup_hash": dedup_hash,
        "transaction_type": TransactionType.EXPENSE.value,
        "is_transfer": False,
    }
    fields.update(values)
    return Transaction(**fields)


def test_transaction_attention_counts_match_review_queues(db_session) -> None:
    db_session.add_all(
        [
            _transaction(dedup_hash="attention-category"),
            _transaction(
                dedup_hash="attention-rejected-category",
                category_suggestion_rejected=True,
            ),
            _transaction(
                dedup_hash="attention-type",
                category="Zakupy",
                transaction_type_predicted=TransactionType.DEBT_PAYMENT.value,
            ),
            _transaction(
                dedup_hash="attention-confirmed-type",
                category="Zakupy",
                transaction_type_predicted=TransactionType.DEBT_PAYMENT.value,
                transaction_type_confirmation_method="manual",
            ),
        ]
    )
    db_session.commit()

    category_reviews, type_reviews = attention._transaction_review_counts(db_session)

    assert category_reviews == 1
    assert type_reviews == 1


def test_attention_summary_endpoint_returns_only_aggregates(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(attention, "_pending_anomaly_count", lambda _session: 3)
    monkeypatch.setattr(attention, "_pending_subscription_count", lambda _session: 2)
    monkeypatch.setattr(attention, "count_items_needing_review", lambda _session: 4)

    response = client.get("/stats/attention-summary")

    assert response.status_code == 200
    assert response.json() == {
        "transaction_reviews": 0,
        "transaction_category_reviews": 0,
        "transaction_type_reviews": 0,
        "anomaly_reviews": 3,
        "subscription_reviews": 2,
        "asset_reviews": 4,
    }
