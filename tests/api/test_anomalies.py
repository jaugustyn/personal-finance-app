"""API regression tests for anomaly response shape and transfer filtering."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from finance.domain.models import Transaction


def _tx(day: int, *, amount: Decimal, merchant: str, is_transfer: bool = False) -> Transaction:
    return Transaction(
        booking_date=date(2026, 1, 1) + timedelta(days=day),
        amount=amount,
        currency="PLN",
        direction="debit",
        merchant=merchant,
        title="",
        category="food",
        source="pekao",
        dedup_hash=f"{merchant}-{day}-{amount}",
        is_transfer=is_transfer,
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
    assert "Own transfer" not in {row["merchant"] for row in rows}
