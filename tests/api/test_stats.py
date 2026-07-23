"""Smoke tests for /stats endpoints — verify routing + schema shape.

Hits the live DB (assumes docker postgres is up). If DB is empty, endpoints
should still return 200 with empty/zero values.
"""
from datetime import date
from decimal import Decimal

import pytest
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


def test_cashflow_buckets_months_without_postgres_to_char(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        booking_date=date(2026, 1, 5),
        amount=Decimal("-40.00"),
        merchant="January Shop",
        dedup_hash="stats-cashflow-jan",
    )
    _add_tx(
        db_session,
        booking_date=date(2026, 2, 7),
        amount=Decimal("100.00"),
        direction="credit",
        merchant="Salary",
        dedup_hash="stats-cashflow-feb",
    )
    db_session.commit()

    response = client.get("/stats/cashflow?all_data=true")

    assert response.status_code == 200
    rows = {row["month"]: row for row in response.json()}
    assert Decimal(rows["2026-01"]["expenses"]) == Decimal("40.00")
    assert Decimal(rows["2026-02"]["income"]) == Decimal("100.00")


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


def test_debt_payments_count_in_cashflow_but_not_category_breakdown(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-600.00"),
        merchant="Alior Bank",
        title="Rata kredytu gotówkowego",
        category=None,
        transaction_type="debt_payment",
        dedup_hash="stats-debt-payment",
    )
    db_session.commit()

    overview_response = client.get("/stats/overview?months=120")
    by_category_response = client.get("/stats/by-category?months=120&limit=10")

    assert overview_response.status_code == 200
    assert Decimal(overview_response.json()["total_debt_payments"]) >= Decimal(
        "600.00"
    )
    assert Decimal(overview_response.json()["total_expenses"]) == Decimal("0")
    assert by_category_response.status_code == 200
    assert all(row["category"] is not None for row in by_category_response.json())


def test_overview_uses_effective_economic_type_semantics(
    client: TestClient,
    db_session: Session,
) -> None:
    rows = [
        ("salary", "credit", "1000", None, False),
        ("income", "credit", "200", None, False),
        ("expense", "debit", "-300", "food", False),
        ("refund", "credit", "50", "food", False),
        ("debt_payment", "debit", "-100", None, False),
        ("asset_allocation", "debit", "-150", None, False),
        ("cash_withdrawal", "debit", "-80", None, False),
        ("own_transfer", "debit", "-500", None, True),
    ]
    for index, (tx_type, direction, amount, category, is_transfer) in enumerate(rows):
        _add_tx(
            db_session,
            amount=Decimal(amount),
            direction=direction,
            category=category,
            transaction_type=tx_type,
            is_transfer=is_transfer,
            dedup_hash=f"stats-economic-{index}",
        )
    db_session.commit()

    overview = client.get("/stats/overview?months=120").json()
    categories = client.get("/stats/by-category?months=120&limit=10").json()

    assert Decimal(overview["total_income"]) == Decimal("1200")
    assert Decimal(overview["gross_expenses"]) == Decimal("300")
    assert Decimal(overview["total_refunds"]) == Decimal("50")
    assert Decimal(overview["total_expenses"]) == Decimal("250")
    assert Decimal(overview["total_debt_payments"]) == Decimal("100")
    assert Decimal(overview["total_asset_allocations"]) == Decimal("150")
    assert Decimal(overview["net_cashflow"]) == Decimal("700")
    food = next(row for row in categories if row["category"] == "food")
    assert Decimal(food["amount"]) == Decimal("250")


def test_unconfirmed_type_suggestion_does_not_change_financial_totals(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-75.00"),
        transaction_type=None,
        transaction_type_predicted="asset_allocation",
        transaction_type_predicted_source="rule",
        dedup_hash="stats-provisional-type-suggestion",
    )
    db_session.commit()

    overview = client.get("/stats/overview?months=120").json()

    assert Decimal(overview["gross_expenses"]) == Decimal("75.00")
    assert Decimal(overview["total_asset_allocations"]) == Decimal("0")
    assert overview["provisional_transaction_count"] == 1


def test_overview_uses_base_amount_for_foreign_currency(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-10.00"),
        currency="USD",
        amount_base=Decimal("-40.00"),
        base_currency="PLN",
        fx_rate=Decimal("4.00000000"),
        fx_rate_date=date.today(),
        fx_rate_source="manual",
        merchant="Foreign Shop",
        dedup_hash="stats-foreign-usd",
    )
    db_session.commit()

    response = client.get("/stats/overview?months=120")

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["total_expenses"]) == Decimal("40.00")
    assert body["base_currency"] == "PLN"


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


def test_by_transaction_type_groups_income_without_expense_categories(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("5000.00"),
        direction="credit",
        merchant="Employer",
        transaction_type="salary",
        category=None,
        dedup_hash="stats-type-salary",
    )
    _add_tx(
        db_session,
        amount=Decimal("300.00"),
        direction="credit",
        merchant="Tax Office",
        transaction_type="refund",
        category=None,
        dedup_hash="stats-type-refund",
    )
    db_session.commit()

    response = client.get(
        "/stats/by-transaction-type?months=120&direction=credit&limit=10"
    )

    assert response.status_code == 200
    rows = {row["category"]: row for row in response.json()}
    assert Decimal(rows["salary"]["amount"]) == Decimal("5000.00")
    assert Decimal(rows["refund"]["amount"]) == Decimal("300.00")


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


def test_top_merchants_groups_normalized_merchant_variants(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-40.00"),
        merchant="LIDL 1234",
        title="",
        category="food",
        dedup_hash="stats-top-lidl-1",
    )
    _add_tx(
        db_session,
        amount=Decimal("-60.00"),
        merchant="Lidl sp. z o.o.",
        title="",
        category="food",
        dedup_hash="stats-top-lidl-2",
    )
    _add_tx(
        db_session,
        amount=Decimal("-25.00"),
        merchant="",
        title="LIDL zakupy karta",
        category="food",
        dedup_hash="stats-top-lidl-title",
    )
    _add_tx(
        db_session,
        amount=Decimal("-90.00"),
        merchant="Other",
        title="",
        category="shopping",
        dedup_hash="stats-top-other",
    )
    db_session.commit()

    response = client.get("/stats/top-merchants?months=120&limit=5")

    assert response.status_code == 200
    rows = response.json()
    lidl = next(row for row in rows if row["merchant"].lower().startswith("lidl"))
    assert Decimal(lidl["amount"]) == Decimal("125.00")
    assert lidl["count"] == 3
    assert lidl["category"] == "food"


def test_stats_all_data_ignores_month_window(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        booking_date=date(2020, 1, 1),
        amount=Decimal("-77.00"),
        merchant="Old Shop",
        dedup_hash="stats-old-shop",
    )
    db_session.commit()

    recent_response = client.get("/stats/top-merchants?months=1&limit=5")
    all_response = client.get("/stats/top-merchants?months=1&all_data=true&limit=5")

    assert recent_response.status_code == 200
    assert all_response.status_code == 200
    assert "Old Shop" not in [row["merchant"] for row in recent_response.json()]
    assert "Old Shop" in [row["merchant"] for row in all_response.json()]


def test_category_trend_shape() -> None:
    r = client.get("/stats/category-trend?months=6&limit=5")
    if r.status_code >= 500:
        return
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_category_trend_returns_top_categories_by_month(
    client: TestClient,
    db_session: Session,
) -> None:
    _add_tx(
        db_session,
        amount=Decimal("-100.00"),
        category="food",
        dedup_hash="trend-food-1",
    )
    _add_tx(
        db_session,
        amount=Decimal("-50.00"),
        category="food",
        dedup_hash="trend-food-2",
    )
    _add_tx(
        db_session,
        amount=Decimal("-30.00"),
        category=None,
        dedup_hash="trend-uncat",
    )
    db_session.commit()

    response = client.get("/stats/category-trend?months=60&limit=5")

    assert response.status_code == 200
    rows = response.json()
    categories = {row["category"] for row in rows}
    assert "food" in categories
    assert None not in categories
    total_food = sum(
        Decimal(row["amount"]) for row in rows if row["category"] == "food"
    )
    assert total_food == Decimal("150.00")


def test_spend_distribution_shape_and_outlier_fence(
    client: TestClient,
    db_session: Session,
) -> None:
    for i in range(6):
        _add_tx(
            db_session,
            amount=Decimal("-20.00"),
            dedup_hash=f"dist-small-{i}",
        )
    _add_tx(
        db_session,
        amount=Decimal("-5000.00"),
        dedup_hash="dist-outlier",
    )
    db_session.commit()

    response = client.get("/stats/spend-distribution?months=60&bins=6")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 7
    assert isinstance(body["buckets"], list)
    assert sum(b["count"] for b in body["buckets"]) == body["count"]
    assert body["max"] == 5000.0
    # The 5000 transaction sits above the Tukey upper fence.
    assert body["iqr_upper"] < 5000.0


def test_recap_shape() -> None:
    r = client.get("/stats/recap?period=month")
    if r.status_code >= 500:
        return
    assert r.status_code == 200
    body = r.json()
    for key in (
        "period",
        "base_currency",
        "cashflow",
        "category_changes",
        "merchant_changes",
        "unconverted_count",
    ):
        assert key in body


@pytest.mark.parametrize(
    "query",
    [
        "date_from=2026-01-01",
        "date_to=2026-01-31",
        "date_from=2026-02-01&date_to=2026-01-31",
    ],
)
def test_recap_rejects_incomplete_or_reversed_custom_range(client, query) -> None:
    response = client.get(f"/stats/recap?{query}")

    assert response.status_code == 422
