"""Transactional account API and import reassignment contract."""

import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from finance.domain.models import Account, Import, Transaction


def _transaction(*, account_id: int, dedup_hash: str, import_id: int | None = None):
    return Transaction(
        account_id=account_id,
        import_id=import_id,
        booking_date=date(2026, 7, 1),
        amount=Decimal("-10.00"),
        currency="PLN",
        direction="debit",
        merchant="Test merchant",
        title="Test transaction",
        source="manual",
        dedup_hash=dedup_hash,
    )


def test_account_crud_normalizes_names_and_prevents_duplicates(client) -> None:
    created = client.post(
        "/accounts",
        json={"name": "  Pekao   osobiste  ", "kind": "bank"},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Pekao osobiste"
    assert created.json()["currency"] == "PLN"

    duplicate = client.post(
        "/accounts",
        json={"name": "pekao OSOBISTE", "kind": "savings"},
    )
    assert duplicate.status_code == 409

    account_id = created.json()["id"]
    updated = client.patch(
        f"/accounts/{account_id}",
        json={"name": "Pekao główne", "kind": "savings"},
    )
    assert updated.status_code == 200
    assert updated.json()["kind"] == "savings"

    archived = client.post(f"/accounts/{account_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert all(row["id"] != account_id for row in client.get("/accounts").json())
    assert any(
        row["id"] == account_id
        for row in client.get("/accounts", params={"include_archived": True}).json()
    )

    restored = client.post(f"/accounts/{account_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None


def test_archived_account_rejects_manual_transaction(client) -> None:
    assert client.post("/accounts/1/archive").status_code == 200
    response = client.post(
        "/transactions",
        json={
            "account_id": 1,
            "booking_date": "2026-07-01",
            "amount": "10.00",
            "direction": "debit",
            "merchant": "Test",
            "title": "",
        },
    )
    assert response.status_code == 422


def test_archived_account_rejects_import(client) -> None:
    assert client.post("/accounts/1/archive").status_code == 200
    response = client.post(
        "/imports",
        files={
            "file": (
                "manual.csv",
                io.BytesIO(b"Date,Amount,Currency,Description\n2026-07-01,-10,PLN,Test\n"),
                "text/csv",
            )
        },
        data={"source": "generic", "account_id": "1"},
    )
    assert response.status_code == 422


def test_account_row_aggregates_imports_transactions_and_currencies(
    client,
    db_session,
) -> None:
    import_row = Import(
        account_id=1,
        source="revolut",
        filename="multi.csv",
        total_rows=2,
        inserted=2,
        duplicates=0,
        created_at=datetime(2026, 7, 2, 10, 30, tzinfo=UTC),
    )
    db_session.add(import_row)
    db_session.flush()
    first = _transaction(account_id=1, dedup_hash="account-pln", import_id=import_row.id)
    second = _transaction(account_id=1, dedup_hash="account-eur", import_id=import_row.id)
    second.currency = "EUR"
    db_session.add_all([first, second])
    db_session.commit()

    row = next(item for item in client.get("/accounts").json() if item["id"] == 1)
    assert row["transaction_count"] == 2
    assert row["import_count"] == 1
    assert row["currencies"] == ["EUR", "PLN"]
    assert row["last_transaction_date"] == "2026-07-01"
    assert row["last_imported_at"].startswith("2026-07-02T10:30:00")


def test_transaction_deduplication_is_scoped_to_account(db_session) -> None:
    second_account = Account(
        name="Second account",
        kind="bank",
        source="unknown",
        currency="PLN",
    )
    db_session.add(second_account)
    db_session.flush()
    db_session.add_all(
        [
            _transaction(account_id=1, dedup_hash="shared-operation"),
            _transaction(account_id=second_account.id, dedup_hash="shared-operation"),
        ]
    )
    db_session.commit()

    db_session.add(
        _transaction(account_id=second_account.id, dedup_hash="shared-operation")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_import_account_change_is_atomic_and_detects_conflict(client, db_session) -> None:
    target = Account(name="Target", kind="bank", source="unknown", currency="PLN")
    source_import = Import(
        account_id=1,
        source="pekao",
        filename="source.csv",
        total_rows=1,
        inserted=1,
        duplicates=0,
    )
    db_session.add_all([target, source_import])
    db_session.flush()
    original = _transaction(
        account_id=1,
        import_id=source_import.id,
        dedup_hash="same-operation",
    )
    conflict = _transaction(account_id=target.id, dedup_hash="same-operation")
    db_session.add_all([original, conflict])
    db_session.commit()

    response = client.patch(
        f"/imports/{source_import.id}/account",
        json={"account_id": target.id},
    )
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(Import, source_import.id).account_id == 1
    assert db_session.get(Transaction, original.id).account_id == 1

    db_session.delete(conflict)
    db_session.commit()
    moved = client.patch(
        f"/imports/{source_import.id}/account",
        json={"account_id": target.id},
    )
    assert moved.status_code == 200
    db_session.expire_all()
    assert db_session.get(Import, source_import.id).account_id == target.id
    assert db_session.get(Transaction, original.id).account_id == target.id


def test_account_filter_scopes_list_summary_and_export(client, db_session) -> None:
    target = Account(name="Second", kind="bank", source="unknown", currency="PLN")
    db_session.add(target)
    db_session.flush()
    first = _transaction(account_id=1, dedup_hash="first-account")
    second = _transaction(account_id=target.id, dedup_hash="second-account")
    second.amount = Decimal("-25.00")
    db_session.add_all([first, second])
    db_session.commit()

    params = {"account_id": target.id}
    rows = client.get("/transactions", params=params)
    assert rows.status_code == 200
    assert [row["id"] for row in rows.json()] == [second.id]
    assert rows.json()[0]["account_name"] == "Second"

    summary = client.get("/transactions/filter-summary", params=params).json()
    assert summary["count"] == 1
    assert Decimal(str(summary["total_expenses"])) == Decimal("25.00")

    exported = client.get("/transactions/export.csv", params=params)
    export_rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(export_rows) == 1
    assert export_rows[0]["account_id"] == str(target.id)
    assert export_rows[0]["account_name"] == "Second"
