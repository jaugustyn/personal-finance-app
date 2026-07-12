"""API regression tests for anomaly response shape and transfer filtering."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from finance.domain.models import Transaction


def _tx(
    day: int,
    *,
    amount: Decimal,
    merchant: str,
    is_transfer: bool = False,
    category: str | None = "food",
    transaction_type: str = "expense",
) -> Transaction:
    return Transaction(
        booking_date=date(2026, 1, 1) + timedelta(days=day),
        amount=amount,
        currency="PLN",
        direction="debit",
        merchant=merchant,
        title="",
        category=category,
        source="pekao",
        dedup_hash=f"{merchant}-{day}-{amount}",
        is_transfer=is_transfer,
        transaction_type=transaction_type,
    )


def test_anomalies_return_reason_list_and_exclude_transfers(client, db_session) -> None:
    for idx in range(30):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.add(_tx(31, amount=Decimal("-2500"), merchant="Real anomaly"))
    db_session.add(
        _tx(32, amount=Decimal("-9999"), merchant="Own transfer", is_transfer=True)
    )
    db_session.commit()

    response = client.get("/anomalies", params={"direction": "debit", "limit": 20})

    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(isinstance(row["reasons"], list) for row in rows)
    assert {
        "anomaly_type",
        "priority_score",
        "reason_codes",
        "merchant_occurrences",
        "merchant_median_amount",
        "is_recurring_merchant",
    }.issubset(rows[0])
    assert "Own transfer" not in {row["merchant"] for row in rows}


def test_anomaly_feedback_endpoint_updates_quality_summary(client, db_session) -> None:
    tx = _tx(1, amount=Decimal("-2500"), merchant="Real anomaly")
    db_session.add(tx)
    db_session.commit()

    response = client.post(f"/anomalies/{tx.id}/feedback", json={"action": "relevant"})

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
    summary = client.get("/transactions/review-summary").json()
    assert summary["anomaly_feedback"]["reviewed"] == 1
    assert summary["anomaly_feedback"]["relevant"] == 1


def test_anomalies_review_hides_model_only_by_default(client, db_session) -> None:
    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.commit()

    hidden = client.get(
        "/anomalies",
        params={"direction": "debit", "contamination": 0.2},
    )
    shown = client.get(
        "/anomalies",
        params={
            "direction": "debit",
            "contamination": 0.2,
            "include_model_only": True,
            "mode": "all",
        },
    )

    assert hidden.status_code == 200
    assert all(row["anomaly_type"] != "model_only" for row in hidden.json())
    assert shown.status_code == 200
    assert any(row["anomaly_type"] == "model_only" for row in shown.json())


def test_anomalies_suspicious_mode_is_stricter(client, db_session) -> None:
    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.add(
        _tx(50, amount=Decimal("-2500"), merchant="Large but known category")
    )
    db_session.add(
        _tx(51, amount=Decimal("-20000"), merchant="", category=None)
    )
    db_session.commit()

    response = client.get("/anomalies", params={"mode": "suspicious", "limit": 20})

    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(
        row["anomaly_type"] in {"suspicious", "data_quality", "merchant_amount_outlier"}
        for row in rows
    )


def test_anomaly_ignore_merchant_removes_future_default_results(client, db_session) -> None:
    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    anomaly = _tx(50, amount=Decimal("-5000"), merchant="KIP")
    db_session.add(anomaly)
    db_session.commit()

    before = client.get("/anomalies", params={"limit": 20})
    assert before.status_code == 200
    assert "KIP" in {row["merchant"] for row in before.json()}

    feedback = client.post(
        f"/anomalies/{anomaly.id}/feedback",
        json={"action": "ignore_merchant"},
    )
    assert feedback.status_code == 200

    after = client.get("/anomalies", params={"limit": 20})
    assert after.status_code == 200
    assert "KIP" not in {row["merchant"] for row in after.json()}
