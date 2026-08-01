"""API regression tests for anomaly response shape and transfer filtering."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from finance.domain.models import MerchantAlias, Transaction
from finance.ml.anomaly import service as anomaly_service


def _tx(
    day: int,
    *,
    amount: Decimal,
    merchant: str,
    is_transfer: bool = False,
    category: str | None = "food",
    transaction_type: str | None = None,
    direction: str = "debit",
) -> Transaction:
    effective_type = transaction_type or ("refund" if direction == "credit" else "expense")
    return Transaction(
        booking_date=date(2026, 1, 1) + timedelta(days=day),
        amount=amount,
        amount_base=amount,
        currency="PLN",
        base_currency="PLN",
        direction=direction,
        merchant=merchant,
        title="",
        category=category,
        source="pekao",
        dedup_hash=f"{merchant}-{day}-{amount}-{direction}",
        is_transfer=is_transfer,
        transaction_type=effective_type,
    )


def test_anomalies_return_reason_list_and_exclude_transfers(client, db_session) -> None:
    for idx in range(30):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.add(_tx(31, amount=Decimal("-2500"), merchant="Real anomaly"))
    db_session.add(_tx(32, amount=Decimal("-9999"), merchant="Own transfer", is_transfer=True))
    unconverted = _tx(
        33,
        amount=Decimal("-99999"),
        merchant="Missing conversion",
    )
    unconverted.amount_base = None
    unconverted.base_currency = None
    unconverted.currency = "USD"
    db_session.add(unconverted)
    db_session.commit()

    response = client.get("/anomalies", params={"direction": "debit", "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    rows = payload["items"]
    assert rows
    assert payload["total"] == payload["pending_total"]
    assert payload["reviewed_total"] == 0
    assert all(isinstance(row["reasons"], list) for row in rows)
    assert {
        "anomaly_type",
        "priority_score",
        "base_currency",
        "reason_codes",
        "merchant_occurrences",
        "merchant_median_amount",
        "is_recurring_merchant",
    }.issubset(rows[0])
    assert {row["base_currency"] for row in rows} == {"PLN"}
    assert "Own transfer" not in {row["merchant"] for row in rows}
    assert "Missing conversion" not in {row["merchant"] for row in rows}


def test_anomaly_frame_uses_only_saved_aliases_for_merchant_identity(
    db_session,
) -> None:
    db_session.add_all(
        [
            MerchantAlias(
                alias_key="shop north",
                alias_label="Shop North",
                canonical_key="shop",
                canonical_label="Shop",
            ),
            MerchantAlias(
                alias_key="shop south",
                alias_label="Shop South",
                canonical_key="shop",
                canonical_label="Shop",
            ),
            _tx(1, amount=Decimal("-40"), merchant="Shop North"),
            _tx(2, amount=Decimal("-50"), merchant="Shop South"),
            _tx(3, amount=Decimal("-60"), merchant="Shop Other"),
        ]
    )
    db_session.commit()

    frame = anomaly_service._transaction_frame(
        db_session,
        date_from=None,
        date_to=None,
    )

    assert frame.loc[frame["merchant"] == "Shop North", "merchant_key"].item() == "shop"
    assert frame.loc[frame["merchant"] == "Shop South", "merchant_key"].item() == "shop"
    assert (
        frame.loc[frame["merchant"] == "Shop Other", "merchant_key"].item()
        == "shop other"
    )


def test_anomaly_feedback_endpoint_updates_quality_summary(client, db_session) -> None:
    from finance.ml.anomaly.service import anomaly_feedback_statuses

    tx = _tx(1, amount=Decimal("-2500"), merchant="Real anomaly")
    db_session.add(tx)
    db_session.commit()

    response = client.post(f"/anomalies/{tx.id}/feedback", json={"action": "relevant"})

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
    summary = client.get("/transactions/review-summary").json()
    assert summary["anomaly_feedback"]["reviewed"] == 1
    assert summary["anomaly_feedback"]["relevant"] == 1
    assert anomaly_feedback_statuses(db_session, {tx.id}) == {tx.id: "relevant"}

    changed = client.post(f"/anomalies/{tx.id}/feedback", json={"action": "not_relevant"})
    assert changed.status_code == 200
    changed_summary = client.get("/transactions/review-summary").json()
    assert changed_summary["anomaly_feedback"]["reviewed"] == 1
    assert changed_summary["anomaly_feedback"]["relevant"] == 0
    assert changed_summary["anomaly_feedback"]["not_relevant"] == 1

    restored = client.post(f"/anomalies/{tx.id}/feedback", json={"action": "restore"})
    assert restored.status_code == 200
    restored_summary = client.get("/transactions/review-summary").json()
    assert restored_summary["anomaly_feedback"]["reviewed"] == 0


def test_anomalies_review_hides_model_only_by_default(client, db_session) -> None:
    from finance.ml.anomaly.service import list_anomaly_rows

    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.commit()

    hidden = list_anomaly_rows(
        db_session,
        direction="debit",
        contamination=0.2,
    )
    shown = list_anomaly_rows(
        db_session,
        direction="debit",
        contamination=0.2,
        include_model_only=True,
        mode="all",
    )

    assert all(row.anomaly_type != "model_only" for row in hidden)
    assert any(row.anomaly_type == "model_only" for row in shown)


def test_anomalies_suspicious_mode_is_stricter(client, db_session) -> None:
    from finance.ml.anomaly.service import list_anomaly_rows

    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.add(_tx(50, amount=Decimal("-2500"), merchant="Large but known category"))
    db_session.add(_tx(51, amount=Decimal("-20000"), merchant="", category=None))
    db_session.commit()

    rows = list_anomaly_rows(db_session, mode="suspicious", limit=20)
    assert rows
    assert all(
        row.anomaly_type in {"suspicious", "data_quality", "merchant_amount_outlier"}
        for row in rows
    )


def test_anomaly_review_hides_transaction_after_decision(client, db_session) -> None:
    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    anomaly = _tx(50, amount=Decimal("-5000"), merchant="KIP")
    db_session.add(anomaly)
    db_session.commit()

    before = client.get("/anomalies", params={"limit": 20})
    assert before.status_code == 200
    assert "KIP" in {row["merchant"] for row in before.json()["items"]}

    feedback = client.post(
        f"/anomalies/{anomaly.id}/feedback",
        json={"action": "not_relevant"},
    )
    assert feedback.status_code == 200

    after = client.get("/anomalies", params={"limit": 20})
    assert after.status_code == 200
    assert "KIP" not in {row["merchant"] for row in after.json()["items"]}
    assert after.json()["reviewed_total"] == 1

    history = client.get(
        "/anomalies",
        params={"limit": 20, "review_state": "reviewed"},
    )
    assert history.status_code == 200
    reviewed = next(row for row in history.json()["items"] if row["id"] == anomaly.id)
    assert reviewed["review_status"] == "not_relevant"
    assert reviewed["reviewed_at"] is not None
    assert reviewed["currently_detected"] is True

    restored = client.post(
        f"/anomalies/{anomaly.id}/feedback",
        json={"action": "restore"},
    )
    assert restored.status_code == 200
    pending_again = client.get("/anomalies", params={"limit": 20}).json()
    assert "KIP" in {row["merchant"] for row in pending_again["items"]}
    assert pending_again["reviewed_total"] == 0


def test_review_history_keeps_transaction_no_longer_detected(client, db_session) -> None:
    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    anomaly = _tx(50, amount=Decimal("-5000"), merchant="Historical anomaly")
    db_session.add(anomaly)
    db_session.commit()

    marked = client.post(
        f"/anomalies/{anomaly.id}/feedback",
        json={"action": "relevant"},
    )
    assert marked.status_code == 200

    anomaly.transaction_type = "own_transfer"
    anomaly.is_transfer = True
    db_session.commit()

    history = client.get(
        "/anomalies",
        params={"review_state": "reviewed"},
    ).json()
    reviewed = next(row for row in history["items"] if row["id"] == anomaly.id)
    assert reviewed["currently_detected"] is False
    assert reviewed["priority_score"] is None
    assert reviewed["reason_codes"] == []

    restored = client.post(
        f"/anomalies/{anomaly.id}/feedback",
        json={"action": "restore"},
    )
    assert restored.status_code == 200
    pending = client.get("/anomalies").json()
    assert anomaly.id not in {row["id"] for row in pending["items"]}
    assert pending["reviewed_total"] == 0


def test_pending_anomalies_do_not_build_review_history_rows(
    client,
    db_session,
    monkeypatch,
) -> None:
    historical = _tx(1, amount=Decimal("-5000"), merchant="Historical")
    db_session.add(historical)
    db_session.commit()
    feedback = client.post(
        f"/anomalies/{historical.id}/feedback",
        json={"action": "relevant"},
    )
    assert feedback.status_code == 200
    historical.transaction_type = "own_transfer"
    historical.is_transfer = True
    db_session.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("pending view should not materialize review history")

    monkeypatch.setattr(anomaly_service, "_historical_review_row", fail_if_called)

    response = client.get("/anomalies", params={"review_state": "pending", "limit": 5})

    assert response.status_code == 200
    assert response.json()["reviewed_total"] == 1


def test_anomaly_totals_do_not_depend_on_limit(client, db_session) -> None:
    for idx in range(40):
        db_session.add(_tx(idx, amount=Decimal("-40"), merchant=f"Shop {idx % 3}"))
    db_session.add(_tx(50, amount=Decimal("-5000"), merchant="Anomaly one"))
    db_session.add(_tx(51, amount=Decimal("-6000"), merchant="Anomaly two"))
    db_session.commit()

    response = client.get("/anomalies", params={"limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["pending_total"] >= 2
    assert payload["total"] == payload["pending_total"]


def test_anomaly_totals_respect_direction(client, db_session) -> None:
    debit_tx = _tx(1, amount=Decimal("-5000"), merchant="Debit anomaly")
    credit_tx = _tx(
        2,
        amount=Decimal("5000"),
        merchant="Credit anomaly",
        direction="credit",
    )
    db_session.add_all([debit_tx, credit_tx])
    db_session.commit()

    for transaction in (debit_tx, credit_tx):
        response = client.post(
            f"/anomalies/{transaction.id}/feedback",
            json={"action": "relevant"},
        )
        assert response.status_code == 200

    debit = client.get(
        "/anomalies",
        params={"direction": "debit", "review_state": "reviewed"},
    ).json()
    credit = client.get(
        "/anomalies",
        params={"direction": "credit", "review_state": "reviewed"},
    ).json()

    assert debit["reviewed_total"] == 1
    assert credit["reviewed_total"] == 1
    assert {row["direction"] for row in debit["items"]} == {"debit"}
    assert {row["direction"] for row in credit["items"]} == {"credit"}
