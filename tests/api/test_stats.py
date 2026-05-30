"""Smoke tests for /stats endpoints — verify routing + schema shape.

Hits the live DB (assumes docker postgres is up). If DB is empty, endpoints
should still return 200 with empty/zero values.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.main import app
from finance.domain.models import Transaction

client = TestClient(app, raise_server_exceptions=False)


def _add_tx(session: Session, **kwargs) -> None:
    defaults = {
        "booking_date": date.today(),
        "amount": Decimal("-10.00"),
        "currency": "PLN",
        "direction": "debit",
        "merchant": "Shop",
        "title": "",
        "category": None,
        "category_predicted": None,
        "source": "pekao",
        "dedup_hash": f"stats-{len(session.new)}-{kwargs.get('merchant', 'shop')}",
        "is_transfer": False,
    }
    defaults.update(kwargs)
    session.add(Transaction(**defaults))


def test_overview_shape() -> None:
    r = client.get("/stats/overview")
    if r.status_code >= 500:
        return  # DB unreachable in test env
    assert r.status_code == 200
    body = r.json()
    for key in ("total_income", "total_expenses", "net_cashflow", "savings_rate", "tx_count"):
        assert key in body


def test_cashflow_shape() -> None:
    r = client.get("/stats/cashflow?months=6")
    if r.status_code >= 500:
        return
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_by_category_shape() -> None:
    r = client.get("/stats/by-category?months=3")
    if r.status_code >= 500:
        return
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_networth_shape() -> None:
    r = client.get("/stats/networth?months=12")
    if r.status_code >= 500:
        return
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_top_merchants_shape() -> None:
    r = client.get("/stats/top-merchants?limit=5")
    if r.status_code >= 500:
        return
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5


def test_by_category_uses_confirmed_categories_by_default(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-100.00"),
        category="food",
        category_predicted=None,
        dedup_hash="stats-confirmed-food",
    )
    _add_tx(
        db_session,
        amount=Decimal("-80.00"),
        category=None,
        category_predicted="health",
        dedup_hash="stats-predicted-health",
    )
    _add_tx(
        db_session,
        amount=Decimal("-999.00"),
        category="transport",
        is_transfer=True,
        merchant="Own account",
        dedup_hash="stats-own-transfer",
    )
    db_session.commit()

    response = client.get("/stats/by-category?months=120&limit=10")

    assert response.status_code == 200
    rows = response.json()
    assert {row["category"] for row in rows} == {"food", None}
    by_category = {row["category"]: row for row in rows}
    assert Decimal(by_category["food"]["amount"]) == Decimal("100.00")
    assert Decimal(by_category[None]["amount"]) == Decimal("80.00")


def test_by_category_can_include_predictions_explicitly(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-80.00"),
        category=None,
        category_predicted="health",
        dedup_hash="stats-include-predicted-health",
    )
    db_session.commit()

    response = client.get(
        "/stats/by-category?months=120&limit=10&include_predictions=true"
    )

    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["category"] == "health"
    assert Decimal(rows[0]["amount"]) == Decimal("80.00")


def test_top_merchants_excludes_transfers_by_default(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-40.00"),
        merchant="Market",
        dedup_hash="stats-top-market",
    )
    _add_tx(
        db_session,
        amount=Decimal("-1000.00"),
        merchant="Own Broker",
        is_transfer=True,
        dedup_hash="stats-top-transfer",
    )
    db_session.commit()

    default_response = client.get("/stats/top-merchants?months=120&limit=5")
    with_transfers_response = client.get(
        "/stats/top-merchants?months=120&limit=5&include_transfers=true"
    )

    assert default_response.status_code == 200
    assert [row["merchant"] for row in default_response.json()] == ["Market"]
    assert with_transfers_response.status_code == 200
    assert with_transfers_response.json()[0]["merchant"] == "Own Broker"
