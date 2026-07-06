from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from finance import assets as assets_mod
from finance.assets import service
from finance.domain.models import Asset, AssetSnapshot, Transaction


@pytest.fixture(autouse=True)
def _stub_quotes(monkeypatch):
    def fake_fetch(symbol: str):
        return assets_mod.Quote(symbol=symbol, price=Decimal("10"), currency="PLN")

    monkeypatch.setattr(assets_mod, "fetch_quote", fake_fetch)


def test_create_asset_refreshes_snapshot(db_session) -> None:
    asset = service.create_asset(
        db_session,
        symbol="abc",
        name="",
        asset_class="equity",
        currency="PLN",
        quantity=Decimal("2"),
        cost_basis=Decimal("15"),
        notes=None,
    )

    assert asset is not None
    view = service.to_asset_view(db_session, asset)
    assert view.symbol == "ABC"
    assert view.last_value_pln == Decimal("20")


def test_portfolio_summary_uses_latest_snapshot(db_session) -> None:
    asset = Asset(symbol="ABC", quantity=Decimal("1"), cost_basis=Decimal("5"))
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        AssetSnapshot(
            asset_id=asset.id,
            snapshot_date=date.today(),
            price=Decimal("10"),
            value_pln=Decimal("10"),
            source="test",
        )
    )
    db_session.commit()

    summary = service.portfolio_summary(db_session)

    assert summary.total_value_pln == Decimal("10")
    assert summary.pnl_pln == Decimal("5")


def test_sankey_returns_income_and_category_nodes(db_session) -> None:
    db_session.add_all(
        [
            Transaction(
                booking_date=date.today(),
                amount=Decimal("-100"),
                currency="PLN",
                direction="debit",
                merchant="Shop",
                title="x",
                category="food",
                source="pekao",
                dedup_hash="flow-1",
            ),
            Transaction(
                booking_date=date.today(),
                amount=Decimal("1000"),
                currency="PLN",
                direction="credit",
                merchant="Employer",
                title="salary",
                source="pekao",
                dedup_hash="flow-2",
            ),
        ]
    )
    db_session.commit()

    nodes, links = service.sankey(
        db_session,
        months=3,
        top_categories=5,
        top_merchants_per_cat=2,
    )

    node_names = {node["name"] for node in nodes}
    assert "Przychody" in node_names
    assert "food" in node_names
    assert links
