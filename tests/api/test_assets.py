"""Tests for /assets CRUD, refresh, history, summary, sankey.

yfinance is monkeypatched with a deterministic stub so tests are offline.
"""
from datetime import date
from decimal import Decimal

import pytest

from finance.assets import Quote
from finance.domain.models import Asset, AssetSnapshot, Transaction


@pytest.fixture(autouse=True)
def _stub_yfinance(monkeypatch):
    """Replace network calls with deterministic stubs."""
    from apps.api.routers import assets as assets_router
    from finance import assets as assets_mod

    def fake_fetch(symbol: str) -> Quote | None:
        # FX pair handler for X-PLN conversions
        if symbol.endswith("PLN=X"):
            base = symbol.replace("PLN=X", "")
            rates = {"USD": Decimal("4.00"), "EUR": Decimal("4.30")}
            return Quote(symbol=symbol, price=rates.get(base, Decimal("1")), currency="PLN")
        prices = {
            "AAPL": (Decimal("200.00"), "USD"),
            "BTC-USD": (Decimal("50000.00"), "USD"),
        }
        if symbol in prices:
            price, currency = prices[symbol]
            return Quote(symbol=symbol, price=price, currency=currency)
        return None

    # Clear FX cache so re-mocking takes effect across tests.
    assets_mod._fx_rate_cached.cache_clear()
    monkeypatch.setattr(assets_mod, "fetch_quote", fake_fetch)
    monkeypatch.setattr(assets_router, "fetch_quote", fake_fetch)
    yield
    assets_mod._fx_rate_cached.cache_clear()


def test_list_assets_empty(client) -> None:
    r = client.get("/assets")
    assert r.status_code == 200
    assert r.json() == []


def test_create_asset_persists_and_snapshots(client) -> None:
    payload = {
        "symbol": "aapl",
        "name": "Apple",
        "asset_class": "equity",
        "currency": "USD",
        "quantity": "2",
        "cost_basis": "1500",
    }
    r = client.post("/assets", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["symbol"] == "AAPL"  # uppercased
    # 2 * 200 USD * 4.00 PLN/USD = 1600 PLN
    assert Decimal(body["last_value_pln"]) == Decimal("1600.00")
    # P/L = 1600 - 1500 = 100
    assert Decimal(body["pnl_pln"]) == Decimal("100.00")


def test_create_asset_duplicate_symbol_409(client) -> None:
    r1 = client.post("/assets", json={"symbol": "AAPL", "quantity": 1})
    assert r1.status_code == 201
    r2 = client.post("/assets", json={"symbol": "AAPL", "quantity": 5})
    assert r2.status_code == 409


def test_patch_asset_updates_quantity(client) -> None:
    r = client.post("/assets", json={"symbol": "AAPL", "quantity": 1, "cost_basis": 800})
    asset_id = r.json()["id"]
    p = client.patch(f"/assets/{asset_id}", json={"quantity": "3"})
    assert p.status_code == 200
    assert Decimal(p.json()["quantity"]) == Decimal("3")


def test_patch_asset_404(client) -> None:
    r = client.patch("/assets/9999", json={"name": "x"})
    assert r.status_code == 404


def test_delete_asset(client) -> None:
    r = client.post("/assets", json={"symbol": "AAPL", "quantity": 1})
    asset_id = r.json()["id"]
    d = client.delete(f"/assets/{asset_id}")
    assert d.status_code == 204
    assert client.get("/assets").json() == []


def test_delete_asset_404(client) -> None:
    assert client.delete("/assets/9999").status_code == 404


def test_summary_aggregates(client) -> None:
    client.post("/assets", json={"symbol": "AAPL", "quantity": 1, "cost_basis": 700})
    client.post("/assets", json={"symbol": "BTC-USD", "quantity": "0.01", "cost_basis": 1500})
    s = client.get("/assets/summary")
    assert s.status_code == 200
    body = s.json()
    # AAPL: 1 * 200 * 4 = 800; BTC: 0.01 * 50000 * 4 = 2000; total = 2800
    assert Decimal(body["total_value_pln"]) == Decimal("2800.00")
    assert Decimal(body["total_cost_pln"]) == Decimal("2200.00")
    assert Decimal(body["pnl_pln"]) == Decimal("600.00")
    assert body["asset_count"] == 2


def test_refresh_endpoint(client, db_session) -> None:
    # create directly to skip auto-snapshot from POST
    a = Asset(
        symbol="AAPL",
        name="Apple",
        asset_class="equity",
        currency="USD",
        quantity=Decimal("1"),
        cost_basis=Decimal("0"),
    )
    db_session.add(a)
    db_session.commit()
    r = client.post("/assets/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["refreshed"] == 1


def test_refresh_skips_unknown_symbol(client, db_session) -> None:
    db_session.add(
        Asset(symbol="ZZZUNKNOWN", asset_class="equity", currency="USD", quantity=Decimal("1"))
    )
    db_session.commit()
    r = client.post("/assets/refresh")
    assert r.status_code == 200
    assert r.json()["skipped"] == 1


def test_history_aggregates_snapshots(client, db_session) -> None:
    a = Asset(symbol="AAPL", currency="USD", quantity=Decimal("1"))
    db_session.add(a)
    db_session.commit()
    db_session.add_all(
        [
            AssetSnapshot(
                asset_id=a.id,
                snapshot_date=date.today(),
                price=Decimal("200"),
                value_pln=Decimal("800"),
                source="test",
            )
        ]
    )
    db_session.commit()
    r = client.get("/assets/history?days=30")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert Decimal(body[0]["value_pln"]) == Decimal("800")


def test_sankey_returns_structure(client, db_session) -> None:
    # seed a few transactions for sankey
    db_session.add_all(
        [
            Transaction(
                booking_date=date.today(),
                amount=Decimal("-100"),
                currency="PLN",
                direction="debit",
                merchant="Carrefour",
                title="x",
                category="food",
                source="pekao",
                dedup_hash="sk-1",
            ),
            Transaction(
                booking_date=date.today(),
                amount=Decimal("5000"),
                currency="PLN",
                direction="credit",
                merchant="Pracodawca",
                title="wypłata",
                source="pekao",
                dedup_hash="sk-2",
            ),
        ]
    )
    db_session.commit()
    r = client.get("/assets/sankey?months=3&top_categories=5&top_merchants_per_cat=3")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "links" in body
    names = [n["name"] for n in body["nodes"]]
    assert "Przychody" in names
    assert "food" in names
    # savings node should appear (income > spent)
    assert "Oszczędności" in names
