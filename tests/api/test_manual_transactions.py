"""API contract for transactions entered directly by the user."""

from datetime import date
from decimal import Decimal

from finance.domain.models import Transaction


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "booking_date": "2026-07-21",
        "amount": "25.50",
        "direction": "debit",
        "merchant": "Sklep osiedlowy",
        "title": "Zakup gotówkowy",
        "transaction_type": None,
        "category": None,
        "notes": "Paragon papierowy",
    }
    payload.update(overrides)
    return payload


def test_create_manual_transaction_uses_pln_and_no_implicit_gold_label(
    client, db_session
) -> None:
    response = client.post("/transactions", json=_payload())

    assert response.status_code == 201
    row = response.json()
    assert row["amount"] == "-25.50"
    assert row["amount_base"] == "-25.50"
    assert row["currency"] == "PLN"
    assert row["base_currency"] == "PLN"
    assert row["source"] == "manual"
    assert row["import_id"] is None
    assert row["transaction_type"] is None
    assert row["transaction_type_effective"] == "expense"
    assert row["transaction_type_confirmation_method"] is None
    assert row["category_confirmation_method"] is None

    stored = db_session.get(Transaction, row["id"])
    assert stored is not None
    assert stored.fx_rate == Decimal("1.00000000")
    assert stored.fx_rate_source == "same_currency"


def test_identical_manual_transactions_are_explicit_distinct_records(
    client, db_session
) -> None:
    first = client.post("/transactions", json=_payload()).json()
    second = client.post("/transactions", json=_payload()).json()

    assert first["id"] != second["id"]
    hashes = {
        row.dedup_hash
        for row in db_session.query(Transaction)
        .filter(Transaction.id.in_([first["id"], second["id"]]))
        .all()
    }
    assert len(hashes) == 2


def test_manual_category_and_type_receive_complete_provenance(
    client, db_session
) -> None:
    response = client.post(
        "/transactions",
        json=_payload(transaction_type="expense", category="food"),
    )

    assert response.status_code == 201
    row = response.json()
    assert row["category"] == "food"
    assert row["category_source"] == "manual"
    assert row["category_confirmation_method"] == "manual"
    assert row["category_confirmed_at"] is not None
    assert row["transaction_type"] == "expense"
    assert row["transaction_type_source"] == "manual"
    assert row["transaction_type_confirmation_method"] == "manual"
    assert row["transaction_type_confirmed_at"] is not None


def test_manual_credit_category_is_a_refund(client, db_session) -> None:
    response = client.post(
        "/transactions",
        json=_payload(
            direction="credit",
            transaction_type="refund",
            category="food",
        ),
    )

    assert response.status_code == 201
    assert response.json()["amount"] == "25.50"
    assert response.json()["transaction_type"] == "refund"


def test_manual_transaction_rejects_incompatible_labels(client, db_session) -> None:
    category_conflict = client.post(
        "/transactions",
        json=_payload(
            direction="credit",
            transaction_type="salary",
            category="food",
        ),
    )
    direction_conflict = client.post(
        "/transactions",
        json=_payload(direction="credit", transaction_type="expense"),
    )

    assert category_conflict.status_code == 422
    assert direction_conflict.status_code == 409
    assert direction_conflict.json()["detail"]["code"] == (
        "transaction_type_direction_mismatch"
    )


def test_edit_manual_transaction_and_reject_core_edit_for_import(client, db_session) -> None:
    created = client.post("/transactions", json=_payload()).json()
    edited = client.patch(
        f"/transactions/{created['id']}",
        json=_payload(
            booking_date="2026-07-22",
            amount="40.00",
            direction="credit",
            transaction_type="income",
            merchant="Zwrot prywatny",
        ),
    )
    assert edited.status_code == 200
    assert edited.json()["booking_date"] == "2026-07-22"
    assert edited.json()["amount"] == "40.00"
    assert edited.json()["transaction_type"] == "income"
    assert edited.json()["transaction_type_confirmation_method"] == "manual"

    imported = Transaction(
        booking_date=date(2026, 7, 21),
        amount=Decimal("-10.00"),
        currency="PLN",
        direction="debit",
        merchant="Bankowy sprzedawca",
        title="Import",
        source="pekao",
        dedup_hash="manual-edit-imported",
    )
    db_session.add(imported)
    db_session.commit()

    blocked = client.patch(f"/transactions/{imported.id}", json=_payload())
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "manual_transaction_required"
