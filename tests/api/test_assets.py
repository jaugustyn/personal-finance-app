"""Contract tests for approximate asset tracking."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from finance.assets import service
from finance.currencies import add_manual_rate
from finance.domain.models import AssetItem, AssetValuation


def _valuation(
    value: str,
    *,
    valuation_date: date | None = None,
    growth_mode: str = "none",
    rate: str | None = None,
    compounding: str | None = None,
    growth_end_date: date | None = None,
) -> dict[str, object]:
    return {
        "valuation_date": (valuation_date or date.today()).isoformat(),
        "input_mode": "total",
        "total_value": value,
        "growth_mode": growth_mode,
        "annual_rate_percent": rate,
        "compounding": compounding,
        "growth_end_date": growth_end_date.isoformat() if growth_end_date else None,
    }


@pytest.mark.parametrize(
    "asset_type",
    [
        "cash",
        "savings_account",
        "deposit",
        "bond",
        "loan_receivable",
        "stock",
        "etf",
        "fund",
        "crypto",
        "precious_metal",
        "other",
    ],
)
def test_all_asset_types_can_be_tracked_as_one_value(client, asset_type: str) -> None:
    response = client.post(
        "/assets/accounts",
        json={
            "name": f"Pozycja {asset_type}",
            "kind": "other",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": asset_type,
            "initial_valuation": _valuation("100"),
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["aggregate_asset_type"] == asset_type
    assert client.get("/assets/overview").json()["breakdown"] == [
        {"asset_type": asset_type, "amount_pln": "100.00", "share": "1.0000"}
    ]


@pytest.mark.parametrize("wrapper", ["ike", "ikze", "ppk"])
def test_retirement_wrappers_are_supported(client, wrapper: str) -> None:
    response = client.post(
        "/assets/accounts",
        json={
            "name": wrapper.upper(),
            "kind": "retirement",
            "wrapper": wrapper,
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "fund",
            "initial_valuation": _valuation("1000"),
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["wrapper"] == wrapper


def test_aggregate_account_exposes_one_value_without_public_item(client) -> None:
    response = client.post(
        "/assets/accounts",
        json={
            "name": "PPK",
            "institution": "Pracodawca",
            "kind": "retirement",
            "wrapper": "ppk",
            "tracking_mode": "aggregate",
            "default_currency": "PLN",
            "aggregate_asset_type": "fund",
            "initial_valuation": _valuation("12500"),
        },
    )

    assert response.status_code == 201, response.text
    account = response.json()
    assert account["amount_pln"] == "12500.00"
    assert account["native_value"] == "12500.00000000"
    assert account["valuation_item_id"] is not None
    assert account["items"] == []

    overview = client.get("/assets/overview").json()
    assert overview["total_pln"] == "12500.00"
    assert overview["account_count"] == 1
    assert overview["item_count"] == 1
    assert overview["breakdown"] == [
        {"asset_type": "fund", "amount_pln": "12500.00", "share": "1.0000"}
    ]


def test_detailed_account_sums_items_and_excludes_missing_fx(client, db_session) -> None:
    today = date.today()
    add_manual_rate(
        db_session,
        currency="EUR",
        base_currency="PLN",
        rate_date=today,
        rate=Decimal("4.50"),
    )
    db_session.commit()
    account = client.post(
        "/assets/accounts",
        json={
            "name": "XTB",
            "kind": "brokerage",
            "tracking_mode": "detailed",
            "default_currency": "PLN",
        },
    ).json()
    cash = client.post(
        f"/assets/accounts/{account['id']}/items",
        json={
            "name": "Gotówka",
            "asset_type": "cash",
            "currency": "PLN",
            "initial_valuation": _valuation("1000"),
        },
    )
    etf = client.post(
        f"/assets/accounts/{account['id']}/items",
        json={
            "name": "ETF światowy",
            "asset_type": "etf",
            "currency": "EUR",
            "symbol": "VWCE",
            "initial_valuation": {
                "valuation_date": today.isoformat(),
                "input_mode": "unit_price",
                "quantity": "2",
                "unit_price": "100",
                "growth_mode": "none",
            },
        },
    )
    assert cash.status_code == 201
    assert etf.status_code == 201, etf.text

    usd_item = service.create_item(
        db_session,
        account["id"],
        name="Krypto",
        asset_type="crypto",
        currency="USD",
        symbol="BTC",
        isin=None,
        review_interval_days=30,
        notes=None,
        initial_valuation={
            "valuation_date": today,
            "input_mode": "total",
            "total_value": Decimal("50"),
            "growth_mode": "none",
        },
        allow_fetch=False,
    )
    assert usd_item is not None

    overview = client.get("/assets/overview").json()
    assert overview["total_pln"] == "1900.00"
    assert overview["unconverted_count"] == 1
    assert overview["item_count"] == 3


def test_fixed_rate_projection_and_maturity() -> None:
    item = AssetItem(
        id=1,
        account_id=1,
        name="Lokata",
        asset_type="deposit",
        currency="PLN",
        review_interval_days=7,
    )
    valuation = AssetValuation(
        id=1,
        item_id=1,
        valuation_date=date(2026, 1, 1),
        input_mode="total",
        total_value=Decimal("10000"),
        currency="PLN",
        amount_pln=Decimal("10000"),
        growth_mode="fixed_rate",
        annual_rate_percent=Decimal("10"),
        compounding="simple",
        growth_end_date=date(2026, 7, 2),
        source="manual",
    )

    before_end = service.value_at(item, [valuation], as_of=date(2026, 4, 2))
    after_end = service.value_at(item, [valuation], as_of=date(2026, 12, 31))

    assert before_end.native_value == Decimal("10249.31506849")
    assert before_end.stale is False
    assert before_end.matured is False
    assert after_end.native_value == Decimal("10498.63013699")
    assert after_end.amount_pln == Decimal("10498.63")
    assert after_end.matured is True


def test_simple_negative_growth_never_reduces_asset_below_zero() -> None:
    item = AssetItem(
        id=1,
        account_id=1,
        name="Aktywo malejące",
        asset_type="deposit",
        currency="PLN",
        review_interval_days=None,
    )
    valuation = AssetValuation(
        id=1,
        item_id=1,
        valuation_date=date(2024, 1, 1),
        input_mode="total",
        total_value=Decimal("100"),
        currency="PLN",
        amount_pln=Decimal("100"),
        growth_mode="fixed_rate",
        annual_rate_percent=Decimal("-50"),
        compounding="simple",
        source="manual",
    )

    result = service.value_at(item, [valuation], as_of=date(2027, 1, 1))

    assert result.native_value == Decimal("0E-8")
    assert result.amount_pln == Decimal("0.00")


def test_loan_receivable_is_counted_as_an_asset(client) -> None:
    response = client.post(
        "/assets/accounts",
        json={
            "name": "Pożyczka udzielona",
            "kind": "other",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "loan_receivable",
            "initial_valuation": _valuation(
                "2500",
                growth_mode="fixed_rate",
                rate="6",
                compounding="simple",
                growth_end_date=date.today() + timedelta(days=365),
            ),
        },
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["aggregate_asset_type"] == "loan_receivable"
    assert created["review_interval_days"] == 30
    overview = client.get("/assets/overview").json()
    assert overview["total_pln"] == "2500.00"
    assert overview["breakdown"] == [
        {
            "asset_type": "loan_receivable",
            "amount_pln": "2500.00",
            "share": "1.0000",
        }
    ]

    updated = client.patch(
        f"/assets/accounts/{created['id']}",
        json={
            "aggregate_asset_type": "loan_receivable",
            "review_interval_days": 180,
            "notes": "Spłata zgodnie z umową",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["aggregate_asset_type"] == "loan_receivable"
    assert updated.json()["review_interval_days"] == 180
    assert updated.json()["notes"] == "Spłata zgodnie z umową"


def test_fixed_growth_is_restricted_to_supported_asset_types(client) -> None:
    unsupported = client.post(
        "/assets/accounts",
        json={
            "name": "ETF z projekcją",
            "kind": "brokerage",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "etf",
            "initial_valuation": _valuation(
                "1000",
                growth_mode="fixed_rate",
                rate="5",
                compounding="monthly",
            ),
        },
    )
    assert unsupported.status_code == 422

    etf = client.post(
        "/assets/accounts",
        json={
            "name": "ETF",
            "kind": "brokerage",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "etf",
            "initial_valuation": _valuation("1000"),
        },
    ).json()
    etf_valuation = client.get(f"/assets/items/{etf['valuation_item_id']}/valuations").json()[0]
    projected_etf = client.put(
        f"/assets/valuations/{etf_valuation['id']}",
        json={
            "growth_mode": "fixed_rate",
            "annual_rate_percent": "5",
            "compounding": "monthly",
        },
    )
    assert projected_etf.status_code == 422

    deposit = client.post(
        "/assets/accounts",
        json={
            "name": "Lokata",
            "kind": "bank",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "deposit",
            "initial_valuation": _valuation(
                "1000",
                growth_mode="fixed_rate",
                rate="5",
                compounding="monthly",
            ),
        },
    )
    assert deposit.status_code == 201, deposit.text

    incompatible_type = client.patch(
        f"/assets/accounts/{deposit.json()['id']}",
        json={"aggregate_asset_type": "etf"},
    )
    assert incompatible_type.status_code == 409


def test_duplicate_valuation_and_tracking_mode_update_are_rejected(client) -> None:
    created = client.post(
        "/assets/accounts",
        json={
            "name": "Oszczędności",
            "kind": "bank",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "savings_account",
            "initial_valuation": _valuation("5000"),
        },
    ).json()
    duplicate = client.post(
        f"/assets/items/{created['valuation_item_id']}/valuations",
        json=_valuation("5100"),
    )
    changed_mode = client.patch(
        f"/assets/accounts/{created['id']}",
        json={"tracking_mode": "detailed"},
    )

    assert duplicate.status_code == 409
    assert changed_mode.status_code == 422


def test_tracking_mode_is_immutable_for_an_empty_account(client, db_session) -> None:
    created = client.post(
        "/assets/accounts",
        json={
            "name": "Pusty rachunek",
            "kind": "brokerage",
            "tracking_mode": "detailed",
        },
    ).json()

    response = client.patch(
        f"/assets/accounts/{created['id']}",
        json={"tracking_mode": "aggregate"},
    )

    assert response.status_code == 422
    account = client.get("/assets/accounts").json()[0]
    assert account["tracking_mode"] == "detailed"
    assert account["valuation_item_id"] is None
    with pytest.raises(service.AssetConflictError):
        service.update_account(
            db_session,
            created["id"],
            {"tracking_mode": "aggregate"},
        )


def test_future_and_oversized_valuations_are_rejected(client) -> None:
    account = client.post(
        "/assets/accounts",
        json={
            "name": "Rachunek testowy",
            "kind": "brokerage",
            "tracking_mode": "detailed",
        },
    ).json()
    item = client.post(
        f"/assets/accounts/{account['id']}/items",
        json={
            "name": "Instrument",
            "asset_type": "other",
            "currency": "PLN",
        },
    ).json()

    future = client.post(
        f"/assets/items/{item['id']}/valuations",
        json=_valuation("100", valuation_date=date.today() + timedelta(days=1)),
    )
    oversized = client.post(
        f"/assets/items/{item['id']}/valuations",
        json={
            "valuation_date": date.today().isoformat(),
            "input_mode": "unit_price",
            "quantity": "9999999999999999.99999999",
            "unit_price": "999999999999.99999999",
            "growth_mode": "none",
        },
    )

    assert future.status_code == 422
    assert oversized.status_code == 422
    assert client.get(f"/assets/items/{item['id']}/valuations").json() == []


def test_history_recalculates_after_edit_delete_and_archive(client) -> None:
    start = date.today() - timedelta(days=10)
    account = client.post(
        "/assets/accounts",
        json={
            "name": "Gotówka",
            "kind": "physical",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "cash",
            "initial_valuation": _valuation("100", valuation_date=start),
        },
    ).json()
    item_id = account["valuation_item_id"]
    second = client.post(
        f"/assets/items/{item_id}/valuations",
        json=_valuation("250", valuation_date=start + timedelta(days=5)),
    )
    assert second.status_code == 201
    valuation_id = second.json()["id"]
    assert client.get("/assets/history?range=3m").json()["points"][-1]["amount_pln"] == "250.00"

    edited = client.put(
        f"/assets/valuations/{valuation_id}",
        json={"total_value": "300"},
    )
    assert edited.status_code == 200, edited.text
    assert client.get("/assets/history?range=3m").json()["points"][-1]["amount_pln"] == "300.00"

    assert client.delete(f"/assets/valuations/{valuation_id}").status_code == 204
    assert client.get("/assets/history?range=3m").json()["points"][-1]["amount_pln"] == "100.00"

    assert client.post(f"/assets/accounts/{account['id']}/archive").status_code == 200
    assert client.get("/assets/overview").json()["total_pln"] == "0.00"
    assert client.get("/assets/history?range=all").json()["points"]


def test_open_ended_fixed_rate_uses_review_interval(client) -> None:
    old = date.today() - timedelta(days=31)
    response = client.post(
        "/assets/accounts",
        json={
            "name": "Konto oszczędnościowe",
            "kind": "bank",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "savings_account",
            "review_interval_days": 30,
            "initial_valuation": _valuation(
                "10000",
                valuation_date=old,
                growth_mode="fixed_rate",
                rate="5",
                compounding="monthly",
            ),
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["stale_count"] == 1
    assert response.json()["amount_pln"] > "10000.00"


def test_archived_items_and_accounts_can_be_restored(client) -> None:
    account = client.post(
        "/assets/accounts",
        json={
            "name": "Rachunek maklerski",
            "kind": "brokerage",
            "tracking_mode": "detailed",
        },
    ).json()
    item = client.post(
        f"/assets/accounts/{account['id']}/items",
        json={
            "name": "ETF",
            "asset_type": "etf",
            "currency": "PLN",
            "initial_valuation": _valuation("1000"),
        },
    ).json()

    assert client.post(f"/assets/items/{item['id']}/archive").status_code == 200
    assert client.get("/assets/overview").json()["total_pln"] == "0.00"
    with_archive = client.get("/assets/accounts?include_archived=true").json()
    assert with_archive[0]["amount_pln"] == "0.00"
    assert with_archive[0]["items"][0]["archived_at"] is not None

    assert client.post(f"/assets/items/{item['id']}/restore").status_code == 200
    assert client.get("/assets/overview").json()["total_pln"] == "1000.00"
    assert client.post(f"/assets/accounts/{account['id']}/archive").status_code == 200
    assert client.get("/assets/overview").json()["total_pln"] == "0.00"
    archived_account = client.get("/assets/accounts?include_archived=true").json()[0]
    assert archived_account["archived_at"] is not None
    assert archived_account["amount_pln"] == "1000.00"
    blocked = client.post(
        f"/assets/items/{item['id']}/valuations",
        json=_valuation("1100", valuation_date=date.today() + timedelta(days=1)),
    )
    assert blocked.status_code == 409

    assert client.post(f"/assets/accounts/{account['id']}/restore").status_code == 200
    assert client.get("/assets/overview").json()["total_pln"] == "1000.00"


def test_valuation_update_can_disable_fixed_growth(client) -> None:
    created = client.post(
        "/assets/accounts",
        json={
            "name": "Lokata",
            "kind": "bank",
            "tracking_mode": "aggregate",
            "aggregate_asset_type": "deposit",
            "initial_valuation": _valuation(
                "10000",
                growth_mode="fixed_rate",
                rate="5",
                compounding="monthly",
            ),
        },
    ).json()
    valuation = client.get(f"/assets/items/{created['valuation_item_id']}/valuations").json()[0]

    response = client.put(
        f"/assets/valuations/{valuation['id']}",
        json={"growth_mode": "none"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["growth_mode"] == "none"
    assert response.json()["annual_rate_percent"] is None
    assert response.json()["compounding"] is None


def test_account_and_item_metadata_can_be_edited(client) -> None:
    account = client.post(
        "/assets/accounts",
        json={
            "name": "Dom maklerski",
            "kind": "brokerage",
            "tracking_mode": "detailed",
        },
    ).json()
    item = client.post(
        f"/assets/accounts/{account['id']}/items",
        json={
            "name": "Fundusz",
            "asset_type": "fund",
            "currency": "PLN",
            "initial_valuation": _valuation("500"),
        },
    ).json()

    updated_account = client.patch(
        f"/assets/accounts/{account['id']}",
        json={"name": "Broker", "institution": "XTB"},
    )
    updated_item = client.patch(
        f"/assets/items/{item['id']}",
        json={
            "name": "ETF globalny",
            "asset_type": "etf",
            "symbol": "VWCE",
            "review_interval_days": 90,
        },
    )

    assert updated_account.status_code == 200, updated_account.text
    assert updated_account.json()["name"] == "Broker"
    assert updated_account.json()["institution"] == "XTB"
    assert updated_item.status_code == 200, updated_item.text
    assert updated_item.json()["name"] == "ETF globalny"
    assert updated_item.json()["asset_type"] == "etf"
    assert updated_item.json()["symbol"] == "VWCE"
    assert updated_item.json()["review_interval_days"] == 90


def test_missing_asset_fx_can_be_recomputed(client, db_session) -> None:
    today = date.today()
    account = client.post(
        "/assets/accounts",
        json={
            "name": "Aktywa zagraniczne",
            "kind": "brokerage",
            "tracking_mode": "detailed",
        },
    ).json()
    item = service.create_item(
        db_session,
        account["id"],
        name="ETF",
        asset_type="etf",
        currency="EUR",
        symbol=None,
        isin=None,
        review_interval_days=30,
        notes=None,
        initial_valuation={
            "valuation_date": today,
            "input_mode": "total",
            "total_value": Decimal("100"),
            "growth_mode": "none",
        },
        allow_fetch=False,
    )
    assert item is not None
    add_manual_rate(
        db_session,
        currency="EUR",
        base_currency="PLN",
        rate_date=today,
        rate=Decimal("4.25"),
    )
    db_session.commit()

    response = client.post("/assets/valuations/recompute-fx")

    assert response.status_code == 200
    assert response.json() == {"updated": 1, "missing": 0}
    assert client.get("/assets/overview").json()["total_pln"] == "425.00"
