"""Synthetic reference scenario shared by SQLite and PostgreSQL tests."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.currencies import MissingFxRate, add_manual_rate, convert_amount
from finance.domain.dto import TransactionDTO
from finance.domain.enums import AccountKind, BankSource
from finance.domain.models import Account, Import, Transaction
from finance.ingestion.generic import GenericCsvParser
from finance.ingestion.policy import build_transaction_values
from finance.ingestion.revolut import RevolutParser
from finance.ingestion.service import compute_dedup_hash
from finance.llm.spending_tools import cashflow_overview, get_spending, top_categories
from finance.ml.classification.dataset import load_training_set

DATE_FROM = date(2026, 4, 1)
DATE_TO = date(2026, 4, 30)
EUR_RATE_DATE = date(2026, 4, 5)
MAIN_ACCOUNT_NAME = "Rachunek główny"
REVOLUT_ACCOUNT_NAME = "Revolut"

GENERIC_COLUMN_MAP = {
    "date": "Date",
    "amount": "Amount",
    "currency": "Currency",
    "merchant": "Merchant",
    "title": "Title",
    "category": "Category",
    "transaction_type": "Operation type",
    "external_id": "External ID",
}


@dataclass(frozen=True)
class ReferenceExpected:
    transaction_count: int = 13
    analytics_transaction_count: int = 11
    income: Decimal = Decimal("5300.00")
    gross_expenses: Decimal = Decimal("460.00")
    refunds: Decimal = Decimal("50.00")
    expenses: Decimal = Decimal("410.00")
    debt_payments: Decimal = Decimal("400.00")
    asset_allocations: Decimal = Decimal("600.00")
    net: Decimal = Decimal("3890.00")
    list_income: Decimal = Decimal("5350.00")
    list_outflows: Decimal = Decimal("2560.00")
    list_net: Decimal = Decimal("2790.00")
    food: Decimal = Decimal("150.00")
    transport: Decimal = Decimal("90.00")
    shopping: Decimal = Decimal("120.00")
    uncategorized_expenses: Decimal = Decimal("50.00")
    unconverted_count: int = 1
    merchant_amounts: tuple[Decimal, ...] = (
        Decimal("200.00"),
        Decimal("120.00"),
        Decimal("90.00"),
        Decimal("50.00"),
    )


@dataclass(frozen=True)
class ReferenceTransaction:
    stable_id: str
    source: str
    booking_datetime: datetime
    amount: Decimal
    currency: str
    merchant: str
    title: str
    raw_transaction_type: str
    raw_category: str = ""
    external_id: str | None = None


@dataclass(frozen=True)
class ReferenceManifest:
    transactions: tuple[ReferenceTransaction, ...]
    expected: ReferenceExpected


REFERENCE_SCENARIO = ReferenceManifest(
    transactions=(
        ReferenceTransaction(
            "salary", "generic", datetime(2026, 4, 1, 8), Decimal("5000.00"),
            "PLN", "Pracodawca testowy", "Wynagrodzenie", "Wynagrodzenie",
            external_id="ref-salary",
        ),
        ReferenceTransaction(
            "income", "generic", datetime(2026, 4, 2, 9), Decimal("300.00"),
            "PLN", "Nadawca testowy", "Dodatkowy wpływ", "Przelew",
            external_id="ref-income",
        ),
        ReferenceTransaction(
            "food", "generic", datetime(2026, 4, 3, 10), Decimal("-200.00"),
            "PLN", "Sklep spożywczy", "Zakupy spożywcze", "Płatność kartą",
            external_id="ref-food",
        ),
        ReferenceTransaction(
            "refund", "generic", datetime(2026, 4, 4, 11), Decimal("50.00"),
            "PLN", "Sklep spożywczy", "Zwrot zakupu", "Zwrot",
            external_id="ref-refund",
        ),
        ReferenceTransaction(
            "eur", "generic", datetime(2026, 4, 5, 12), Decimal("-20.00"),
            "EUR", "Kolej testowa", "Bilet", "Płatność kartą",
            external_id="ref-eur",
        ),
        ReferenceTransaction(
            "usd", "generic", datetime(2026, 4, 6, 13), Decimal("-10.00"),
            "USD", "Sklep USD", "Brak kursu", "Płatność kartą",
            external_id="ref-usd",
        ),
        ReferenceTransaction(
            "own-transfer", "generic", datetime(2026, 4, 7, 14),
            Decimal("-1000.00"), "PLN", "Rachunek własny", "Przelew własny",
            "Przelew", external_id="ref-transfer",
        ),
        ReferenceTransaction(
            "cash", "generic", datetime(2026, 4, 8, 15), Decimal("-100.00"),
            "PLN", "Bankomat testowy", "Wypłata gotówki", "Bankomat",
            external_id="ref-cash",
        ),
        ReferenceTransaction(
            "debt", "generic", datetime(2026, 4, 9, 16), Decimal("-400.00"),
            "PLN", "Bank testowy", "Spłata zobowiązania", "Przelew",
            external_id="ref-debt",
        ),
        ReferenceTransaction(
            "allocation", "generic", datetime(2026, 4, 10, 17),
            Decimal("-600.00"), "PLN", "Rachunek oszczędnościowy",
            "Alokacja środków", "Przelew", external_id="ref-allocation",
        ),
        ReferenceTransaction(
            "shopping", "generic", datetime(2026, 4, 11, 18),
            Decimal("-120.00"), "PLN", "Sklep internetowy", "Zakup",
            "Płatność kartą", raw_category="Zakupy", external_id="ref-shopping",
        ),
        ReferenceTransaction(
            "revolut-morning", "revolut", datetime(2026, 4, 12, 10, 15),
            Decimal("-25.00"), "PLN", "Kawiarnia referencyjna",
            "Płatność kartą", "Płatność kartą",
        ),
        ReferenceTransaction(
            "revolut-evening", "revolut", datetime(2026, 4, 12, 18, 45),
            Decimal("-25.00"), "PLN", "Kawiarnia referencyjna",
            "Płatność kartą", "Płatność kartą",
        ),
    ),
    expected=ReferenceExpected(),
)

EXPECTED = REFERENCE_SCENARIO.expected


def generic_csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(GENERIC_COLUMN_MAP.values())
    for transaction in REFERENCE_SCENARIO.transactions:
        if transaction.source != "generic":
            continue
        writer.writerow(
            (
                transaction.booking_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                format(transaction.amount, ".2f"),
                transaction.currency,
                transaction.merchant,
                transaction.title,
                transaction.raw_category,
                transaction.raw_transaction_type,
                transaction.external_id or "",
            )
        )
    return buffer.getvalue().encode("utf-8")


def revolut_csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(
        (
            "Rodzaj", "Produkt", "Data rozpoczęcia", "Data zrealizowania",
            "Opis", "Kwota", "Opłata", "Waluta", "State", "Saldo",
        )
    )
    balance = Decimal("125.00")
    for transaction in REFERENCE_SCENARIO.transactions:
        if transaction.source != "revolut":
            continue
        balance += transaction.amount
        writer.writerow(
            (
                transaction.raw_transaction_type,
                "Bieżące",
                (transaction.booking_datetime - timedelta(minutes=5)).strftime(
                    "%d.%m.%Y %H:%M"
                ),
                transaction.booking_datetime.strftime("%d.%m.%Y %H:%M"),
                transaction.merchant,
                format(transaction.amount, ".2f"),
                "0.00",
                transaction.currency,
                "ZAKOŃCZONO",
                format(balance, ".2f"),
            )
        )
    return buffer.getvalue().encode("utf-8")


def _parsed_transactions() -> tuple[list[TransactionDTO], list[TransactionDTO]]:
    generic = GenericCsvParser(GENERIC_COLUMN_MAP).parse(
        io.BytesIO(generic_csv_bytes()),
        filename="reference-generic.csv",
    )
    revolut = RevolutParser().parse(
        io.BytesIO(revolut_csv_bytes()),
        filename="reference-revolut.csv",
    )
    return generic, revolut


def seed_sqlite_reference_scenario(session: Session) -> None:
    """Persist parser output with production import policy, without PG upsert."""

    add_manual_rate(
        session,
        currency="EUR",
        base_currency="PLN",
        rate_date=EUR_RATE_DATE,
        rate=Decimal("4.50"),
    )
    main_account = session.get(Account, 1)
    if main_account is None:
        main_account = Account(
            name=MAIN_ACCOUNT_NAME,
            kind=AccountKind.BANK,
            source=BankSource.UNKNOWN,
            currency="PLN",
        )
        session.add(main_account)
    else:
        main_account.name = MAIN_ACCOUNT_NAME
        main_account.kind = AccountKind.BANK
        main_account.source = BankSource.UNKNOWN
    revolut_account = session.scalar(
        select(Account).where(Account.name == REVOLUT_ACCOUNT_NAME)
    )
    if revolut_account is None:
        revolut_account = Account(
            name=REVOLUT_ACCOUNT_NAME,
            kind=AccountKind.BANK,
            source=BankSource.REVOLUT,
            currency="PLN",
        )
        session.add(revolut_account)
    session.flush()

    generic_dtos, revolut_dtos = _parsed_transactions()
    for source, filename, account, dtos in (
        ("unknown", "reference-generic.csv", main_account, generic_dtos),
        ("revolut", "reference-revolut.csv", revolut_account, revolut_dtos),
    ):
        import_row = Import(
            account_id=account.id,
            source=source,
            filename=filename,
            total_rows=len(dtos),
            inserted=len(dtos),
            duplicates=0,
        )
        session.add(import_row)
        session.flush()
        for dto in dtos:
            try:
                converted = convert_amount(
                    session,
                    amount=dto.amount,
                    currency=dto.currency,
                    rate_date=dto.booking_date,
                    allow_fetch=False,
                )
            except MissingFxRate:
                converted = None
            values = build_transaction_values(
                dto,
                converted=converted,
                personal=None,
                account_id=account.id,
                import_id=import_row.id,
                dedup_hash=compute_dedup_hash(dto),
            )
            session.add(Transaction(**values))
    session.commit()


def _ids_by_external_id(session: Session) -> dict[str, int]:
    return {
        str(external_id): int(tx_id)
        for external_id, tx_id in session.execute(
            select(Transaction.external_id, Transaction.id).where(
                Transaction.external_id.is_not(None)
            )
        )
    }


def finalize_reference_scenario(session: Session, client: TestClient) -> dict[str, int]:
    """Apply the same public review operations a user performs after import."""

    ids = _ids_by_external_id(session)
    shopping = session.get(Transaction, ids["ref-shopping"])
    assert shopping is not None
    assert shopping.category is None
    assert str(shopping.category_predicted) == "shopping"
    assert shopping.category_predicted_source == "bank"
    assert shopping.category_predicted_ref
    assert shopping.category_confirmation_method is None
    assert shopping.transaction_type_confirmation_method is None
    before = load_training_set(session)
    assert ids["ref-shopping"] not in set(before.get("transaction_id", []))
    session.rollback()

    type_updates = {
        "ref-salary": "salary",
        "ref-income": "income",
        "ref-transfer": "own_transfer",
        "ref-cash": "cash_withdrawal",
        "ref-debt": "debt_payment",
        "ref-allocation": "asset_allocation",
    }
    for external_id, transaction_type in type_updates.items():
        response = client.patch(
            f"/transactions/{ids[external_id]}/type",
            json={"transaction_type": transaction_type},
        )
        assert response.status_code == 200, response.text

    category_updates = {
        "ref-food": "food",
        "ref-refund": "food",
        "ref-eur": "transport",
    }
    for external_id, category in category_updates.items():
        response = client.patch(
            f"/transactions/{ids[external_id]}/category",
            json={"category": category},
        )
        assert response.status_code == 200, response.text

    response = client.post(
        "/transactions/bulk/accept-suggestions",
        json={"ids": [ids["ref-shopping"]], "manual": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    response = client.patch(
        f"/transactions/{ids['ref-shopping']}/annotations",
        json={
            "notes": '=WEBSERVICE("https://invalid.test")',
            "tags": ["referencyjna", "ważne"],
        },
    )
    assert response.status_code == 200, response.text
    session.expire_all()
    return ids


def assert_transaction_contract(
    session: Session,
    client: TestClient,
    ids: dict[str, int],
) -> None:
    response = client.get(
        "/transactions",
        params={
            "date_from": DATE_FROM.isoformat(),
            "date_to": DATE_TO.isoformat(),
            "limit": 100,
            "sort_by": "amount",
            "sort_direction": "desc",
        },
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == EXPECTED.transaction_count
    assert rows[-1]["merchant_raw"] == "Sklep USD"
    assert {
        row["account_name"] for row in rows if row["source"] == "revolut"
    } == {REVOLUT_ACCOUNT_NAME}
    assert {
        row["account_name"] for row in rows if row["source"] != "revolut"
    } == {MAIN_ACCOUNT_NAME}

    response = client.get(
        "/transactions",
        params={"limit": 100, "sort_by": "amount", "sort_direction": "asc"},
    )
    assert response.json()[-1]["merchant_raw"] == "Sklep USD"

    shopping = session.get(Transaction, ids["ref-shopping"])
    assert shopping is not None
    assert str(shopping.category) == "shopping"
    assert shopping.category_source == "bank"
    assert shopping.category_confirmation_method == "accepted_suggestion"
    assert shopping.category_confirmed_at is not None
    assert shopping.category_origin_ref
    assert str(shopping.transaction_type) == "expense"
    assert shopping.transaction_type_confirmation_method == "accepted_suggestion"
    assert shopping.transaction_type_confirmed_at is not None
    expected_categories = {
        "ref-food": "food",
        "ref-refund": "food",
        "ref-eur": "transport",
    }
    for external_id, expected_category in expected_categories.items():
        transaction = session.get(Transaction, ids[external_id])
        assert transaction is not None
        assert str(transaction.category) == expected_category
        assert transaction.category_source == "manual"
        assert transaction.category_confirmation_method == "manual"
        assert transaction.category_confirmed_at is not None

    expected_types = {
        "ref-salary": "salary",
        "ref-income": "income",
        "ref-transfer": "own_transfer",
        "ref-cash": "cash_withdrawal",
        "ref-debt": "debt_payment",
        "ref-allocation": "asset_allocation",
    }
    for external_id, expected_type in expected_types.items():
        transaction = session.get(Transaction, ids[external_id])
        assert transaction is not None
        assert str(transaction.transaction_type) == expected_type
        assert transaction.transaction_type_source == "manual"
        assert transaction.transaction_type_confirmation_method == "manual"
        assert transaction.transaction_type_confirmed_at is not None
    own_transfer = session.get(Transaction, ids["ref-transfer"])
    assert own_transfer is not None and own_transfer.is_transfer is True

    training = load_training_set(session)
    assert set(training["transaction_id"]) == {
        ids["ref-food"],
        ids["ref-eur"],
        ids["ref-shopping"],
    }

    revolut_times = session.scalars(
        select(Transaction.booking_datetime)
        .where(Transaction.source == "revolut")
        .order_by(Transaction.booking_datetime)
    ).all()
    expected_revolut_times = {
        transaction.booking_datetime
        for transaction in REFERENCE_SCENARIO.transactions
        if transaction.source == "revolut"
    }
    assert set(revolut_times) == expected_revolut_times


def assert_stats_contract(client: TestClient) -> None:
    overview = client.get("/stats/overview", params={"all_data": True})
    assert overview.status_code == 200
    data = overview.json()
    assert Decimal(str(data["total_income"])) == EXPECTED.income
    assert Decimal(str(data["gross_expenses"])) == EXPECTED.gross_expenses
    assert Decimal(str(data["total_refunds"])) == EXPECTED.refunds
    assert Decimal(str(data["total_expenses"])) == EXPECTED.expenses
    assert Decimal(str(data["total_debt_payments"])) == EXPECTED.debt_payments
    assert Decimal(str(data["total_asset_allocations"])) == EXPECTED.asset_allocations
    assert Decimal(str(data["net_cashflow"])) == EXPECTED.net
    assert data["tx_count"] == EXPECTED.analytics_transaction_count
    assert data["unconverted_count"] == EXPECTED.unconverted_count
    expected_savings_rate = float(
        (EXPECTED.income - EXPECTED.expenses - EXPECTED.debt_payments)
        / EXPECTED.income
    )
    assert data["savings_rate"] == pytest.approx(expected_savings_rate)

    cashflow = client.get("/stats/cashflow", params={"all_data": True}).json()
    assert len(cashflow) == 1
    april = cashflow[0]
    assert april["month"] == "2026-04"
    assert Decimal(str(april["income"])) == EXPECTED.income
    assert Decimal(str(april["expenses"])) == EXPECTED.expenses
    assert Decimal(str(april["refunds"])) == EXPECTED.refunds
    assert Decimal(str(april["debt_payments"])) == EXPECTED.debt_payments
    assert Decimal(str(april["asset_allocations"])) == EXPECTED.asset_allocations
    assert Decimal(str(april["net"])) == EXPECTED.net

    summary = client.get(
        "/transactions/filter-summary",
        params={"date_from": DATE_FROM.isoformat(), "date_to": DATE_TO.isoformat()},
    ).json()
    assert summary["count"] == EXPECTED.transaction_count
    assert Decimal(str(summary["total_income"])) == EXPECTED.list_income
    assert Decimal(str(summary["total_expenses"])) == EXPECTED.list_outflows
    assert Decimal(str(summary["net"])) == EXPECTED.list_net
    assert summary["unconverted_count"] == EXPECTED.unconverted_count


def assert_recap_contract(client: TestClient) -> None:
    recap = client.get(
        "/stats/recap",
        params={"date_from": DATE_FROM.isoformat(), "date_to": DATE_TO.isoformat()},
    )
    assert recap.status_code == 200
    recap_cashflow = recap.json()["cashflow"]
    assert Decimal(str(recap_cashflow["income"])) == EXPECTED.income
    assert Decimal(str(recap_cashflow["expenses"])) == EXPECTED.expenses
    assert Decimal(str(recap_cashflow["net"])) == EXPECTED.net
    assert recap.json()["unconverted_count"] == EXPECTED.unconverted_count


def assert_category_and_merchant_contract(client: TestClient) -> None:
    categories = {
        row["category"]: Decimal(str(row["amount"]))
        for row in client.get(
            "/stats/by-category",
            params={"all_data": True, "limit": 20},
        ).json()
    }
    assert categories["food"] == EXPECTED.food
    assert categories["transport"] == EXPECTED.transport
    assert categories["shopping"] == EXPECTED.shopping
    assert categories[None] == EXPECTED.uncategorized_expenses

    merchants = client.get(
        "/stats/top-merchants",
        params={"all_data": True, "limit": 20},
    ).json()
    assert tuple(
        Decimal(str(row["amount"])) for row in merchants
    ) == EXPECTED.merchant_amounts
    assert all(row["merchant"] != "Sklep USD" for row in merchants)


def assert_currency_contract(client: TestClient) -> None:
    response = client.get("/currencies/status")
    assert response.status_code == 200
    status = response.json()
    assert status["base_currency"] == "PLN"
    assert status["missing_rate_count"] == EXPECTED.unconverted_count
    assert status["missing_rates"] == [
        {
            "currency": "USD",
            "base_currency": "PLN",
            "rate_date": "2026-04-06",
            "count": 1,
        }
    ]
    currencies = {row["currency"]: row for row in status["currencies"]}
    expected_currency_counts = {
        currency: sum(
            transaction.currency == currency
            for transaction in REFERENCE_SCENARIO.transactions
        )
        for currency in {"PLN", "EUR", "USD"}
    }
    assert set(currencies) == set(expected_currency_counts)
    for currency, expected_count in expected_currency_counts.items():
        assert currencies[currency]["count"] == expected_count


def assert_export_contract(client: TestClient) -> None:
    response = client.get(
        "/transactions/export.csv",
        params={"date_from": DATE_FROM.isoformat(), "date_to": DATE_TO.isoformat()},
    )
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == EXPECTED.transaction_count
    assert {row["account_name"] for row in rows} == {
        MAIN_ACCOUNT_NAME,
        REVOLUT_ACCOUNT_NAME,
    }
    assert all(row["account_id"] for row in rows)
    by_external_id = {row["external_id"]: row for row in rows if row["external_id"]}
    assert by_external_id["ref-eur"]["amount_base"] == "-90.00"
    assert by_external_id["ref-eur"]["base_currency"] == "PLN"
    assert Decimal(by_external_id["ref-eur"]["fx_rate"]) == Decimal("4.5")
    assert by_external_id["ref-usd"]["amount_base"] == ""
    assert by_external_id["ref-usd"]["base_currency"] == ""
    shopping = by_external_id["ref-shopping"]
    assert shopping["category"] == "shopping"
    assert shopping["category_source"] == "bank"
    assert shopping["category_confirmation_method"] == "accepted_suggestion"
    assert shopping["category_confirmed_at"]
    assert shopping["category_origin_ref"]
    assert shopping["category_predicted"] == ""
    assert shopping["transaction_type"] == "expense"
    assert (
        shopping["transaction_type_confirmation_method"]
        == "accepted_suggestion"
    )
    assert shopping["transaction_type_confirmed_at"]
    food = by_external_id["ref-food"]
    assert food["category_source"] == "manual"
    assert food["category_confirmation_method"] == "manual"
    assert food["category_confirmed_at"]
    assert shopping["notes"].startswith("'=WEBSERVICE")
    assert json.loads(shopping["tags"]) == ["referencyjna", "ważne"]
    revolut_times = {
        row["booking_datetime"] for row in rows if row["source"] == "revolut"
    }
    expected_revolut_times = {
        transaction.booking_datetime.isoformat(sep=" ")
        for transaction in REFERENCE_SCENARIO.transactions
        if transaction.source == "revolut"
    }
    assert revolut_times == expected_revolut_times


def assert_assistant_contract(session: Session, client: TestClient) -> None:
    spending = get_spending(session, {"period": "2026-04"})
    assert spending["total"] == pytest.approx(float(EXPECTED.expenses))
    assert spending["transactions"] == 6
    food = get_spending(session, {"period": "2026-04", "category": "food"})
    assert food["total"] == pytest.approx(float(EXPECTED.food))
    assert food["transactions"] == 2

    categories = top_categories(session, {"period": "2026-04", "limit": 10})
    assert categories["total_candidate_spend"] == pytest.approx(
        float(EXPECTED.expenses)
    )
    categorized = EXPECTED.food + EXPECTED.transport + EXPECTED.shopping
    assert categories["categorized_total"] == pytest.approx(float(categorized))
    assert categories["uncategorized_total"] == pytest.approx(
        float(EXPECTED.uncategorized_expenses)
    )
    assert categories["category_coverage"] == pytest.approx(
        float(categorized / EXPECTED.expenses)
    )

    cashflow = cashflow_overview(session, {"period": "2026-04"})
    assert cashflow["income"] == pytest.approx(float(EXPECTED.income))
    assert cashflow["gross_expenses"] == pytest.approx(
        float(EXPECTED.gross_expenses)
    )
    assert cashflow["refunds"] == pytest.approx(float(EXPECTED.refunds))
    assert cashflow["expenses"] == pytest.approx(float(EXPECTED.expenses))
    assert cashflow["debt_payments"] == pytest.approx(
        float(EXPECTED.debt_payments)
    )
    assert cashflow["asset_allocations"] == pytest.approx(
        float(EXPECTED.asset_allocations)
    )
    assert cashflow["net"] == pytest.approx(float(EXPECTED.net))
    expected_savings_rate = float(
        (EXPECTED.income - EXPECTED.expenses - EXPECTED.debt_payments)
        / EXPECTED.income
    )
    assert cashflow["savings_rate"] == pytest.approx(expected_savings_rate)
    assert cashflow["transactions"] == EXPECTED.analytics_transaction_count

    response = client.post(
        "/chat",
        json={"question": "Jaki miałem cash flow w kwietniu 2026?"},
    )
    assert response.status_code == 200
    answer = response.json()
    assert answer["source"] == "heuristic"
    assert answer["tool"] == "cashflow_overview"
    assert answer["data"]["net"] == pytest.approx(float(EXPECTED.net))
