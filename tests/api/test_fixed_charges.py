"""API and calendar-contract tests for planned fixed charges."""

from datetime import date
from decimal import Decimal

from finance.domain.models import CategoryDef, Transaction
from finance.fixed_charges.service import (
    create_fixed_charge,
    link_fixed_charge_transactions,
    list_fixed_charges,
    next_due_date,
)


def test_fixed_charge_crud_and_pause(client, db_session) -> None:
    created = client.post(
        "/fixed-charges",
        json={
            "name": "  Czynsz   i administracja ",
            "amount": "2100.00",
            "cadence": "monthly",
            "anchor_date": "2099-07-31",
            "category": "housing",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Czynsz i administracja"
    assert body["amount"] == 2100.0
    assert body["currency"] == "PLN"
    assert body["monthly_equivalent"] == 2100.0
    assert body["yearly_cost"] == 25200.0

    listed = client.get("/fixed-charges")
    assert listed.status_code == 200
    assert listed.json()["summary"]["active_count"] == 1
    assert listed.json()["summary"]["monthly_total"] == 2100.0

    charge_id = body["id"]
    paused = client.patch(f"/fixed-charges/{charge_id}", json={"active": False})
    assert paused.status_code == 200
    assert paused.json()["active"] is False
    assert paused.json()["next_due_date"] is None
    assert client.get("/fixed-charges").json()["summary"]["active_count"] == 0

    assert client.delete(f"/fixed-charges/{charge_id}").status_code == 204
    assert client.get("/fixed-charges").json()["items"] == []


def test_fixed_charge_validates_category_and_payload(client) -> None:
    missing_category = client.post(
        "/fixed-charges",
        json={
            "name": "Internet",
            "amount": "70.00",
            "cadence": "monthly",
            "anchor_date": "2026-08-10",
            "category": "missing",
        },
    )
    assert missing_category.status_code == 422

    invalid_amount = client.post(
        "/fixed-charges",
        json={
            "name": "Internet",
            "amount": "0",
            "cadence": "monthly",
            "anchor_date": "2026-08-10",
        },
    )
    assert invalid_amount.status_code == 422


def test_fixed_charge_calendar_keeps_anchor_day() -> None:
    assert next_due_date(
        date(2024, 1, 31),
        "monthly",
        as_of=date(2024, 2, 1),
    ) == date(2024, 2, 29)
    assert next_due_date(
        date(2024, 1, 31),
        "monthly",
        as_of=date(2024, 3, 1),
    ) == date(2024, 3, 31)
    assert next_due_date(
        date(2024, 2, 29),
        "yearly",
        as_of=date(2025, 1, 1),
    ) == date(2025, 2, 28)


def test_fixed_charge_summary_uses_active_rows_and_real_occurrences(db_session) -> None:
    create_fixed_charge(
        db_session,
        name="Czynsz",
        amount=Decimal("2000"),
        cadence="monthly",
        anchor_date=date(2026, 1, 31),
    )
    insurance = create_fixed_charge(
        db_session,
        name="Ubezpieczenie",
        amount=Decimal("1200"),
        cadence="yearly",
        anchor_date=date(2026, 7, 25),
    )
    insurance.active = False
    db_session.commit()

    result = list_fixed_charges(db_session, as_of=date(2026, 7, 20))

    assert result.summary.active_count == 1
    assert result.summary.monthly_total == Decimal("2000.00")
    assert result.summary.yearly_total == Decimal("24000.00")
    assert result.summary.next_30_days_count == 1
    assert result.summary.next_30_days_total == Decimal("2000.00")
    assert result.items[0].next_due_date == date(2026, 7, 31)
    assert result.items[1].next_due_date is None


def test_category_used_by_fixed_charge_cannot_be_deleted(client, db_session) -> None:
    category = CategoryDef(name="education", is_system=False, color="#3b82f6")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    create_fixed_charge(
        db_session,
        name="Kurs językowy",
        amount=Decimal("150"),
        cadence="monthly",
        anchor_date=date(2026, 8, 1),
        category="education",
    )

    response = client.delete(f"/categories/{category.id}")

    assert response.status_code == 409
    assert response.json()["detail"]["fixed_charge_count"] == 1


def _transaction(
    *,
    dedup_hash: str,
    booking_date: date,
    amount: str,
    direction: str = "debit",
) -> Transaction:
    return Transaction(
        booking_date=booking_date,
        amount=Decimal(amount),
        currency="PLN",
        direction=direction,
        merchant="Administracja osiedla",
        title="Opłata miesięczna",
        source="pekao",
        dedup_hash=dedup_hash,
    )


def test_manual_transaction_link_updates_payment_status(client, db_session) -> None:
    today = date.today()
    db_session.add_all(
        [
            _transaction(
                dedup_hash="fixed-link-debit",
                booking_date=today,
                amount="-2050.00",
            ),
            _transaction(
                dedup_hash="fixed-link-credit",
                booking_date=today,
                amount="2050.00",
                direction="credit",
            ),
        ]
    )
    db_session.commit()
    debit = db_session.query(Transaction).filter_by(dedup_hash="fixed-link-debit").one()
    charge = client.post(
        "/fixed-charges",
        json={
            "name": "Czynsz",
            "amount": "2100.00",
            "cadence": "monthly",
            "anchor_date": today.isoformat(),
        },
    ).json()

    available = client.get(f"/fixed-charges/{charge['id']}/transactions")
    assert available.status_code == 200
    assert [item["transaction_id"] for item in available.json()["candidates"]] == [
        debit.id
    ]

    linked = client.post(
        f"/fixed-charges/{charge['id']}/transactions",
        json={
            "transaction_ids": [debit.id],
            "scheduled_due_date": today.isoformat(),
        },
    )
    assert linked.status_code == 200

    row = client.get("/fixed-charges").json()["items"][0]
    assert row["payment_status"] == "paid"
    assert row["current_paid_amount"] == 2050.0
    assert row["linked_transaction_count"] == 1
    assert row["last_payment_date"] == today.isoformat()
    assert client.get("/fixed-charges").json()["summary"]["next_30_days_count"] == 0

    history = client.get(f"/fixed-charges/{charge['id']}/transactions").json()
    assert len(history["linked"]) == 1
    assert history["linked"][0]["scheduled_due_date"] == today.isoformat()

    unlinked = client.delete(
        f"/fixed-charges/{charge['id']}/transactions/{debit.id}"
    )
    assert unlinked.status_code == 204
    restored = client.get("/fixed-charges").json()["items"][0]
    assert restored["payment_status"] == "pending"
    assert restored["linked_transaction_count"] == 0


def test_create_manual_payment_is_linked_atomically(client, db_session) -> None:
    today = date.today()
    charge = client.post(
        "/fixed-charges",
        json={
            "name": "Czynsz",
            "amount": "2100.00",
            "cadence": "monthly",
            "anchor_date": today.isoformat(),
            "category": "housing",
        },
    ).json()

    response = client.post(
        f"/fixed-charges/{charge['id']}/transactions/manual",
        json={
            "scheduled_due_date": today.isoformat(),
            "booking_date": today.isoformat(),
            "amount": "2100.00",
            "direction": "debit",
            "merchant": "Administracja",
            "title": "Czynsz",
            "transaction_type": "expense",
            "category": "housing",
            "notes": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["amount_base"] == -2100.0
    transaction = db_session.get(Transaction, response.json()["transaction_id"])
    assert transaction is not None
    assert transaction.source == "manual"
    assert transaction.category_confirmation_method == "manual"
    assert client.get("/fixed-charges").json()["items"][0]["payment_status"] == "paid"


def test_invalid_manual_payment_does_not_leave_transaction(client, db_session) -> None:
    today = date.today()
    charge = client.post(
        "/fixed-charges",
        json={
            "name": "Internet",
            "amount": "70.00",
            "cadence": "monthly",
            "anchor_date": today.isoformat(),
        },
    ).json()
    before = db_session.query(Transaction).count()

    response = client.post(
        f"/fixed-charges/{charge['id']}/transactions/manual",
        json={
            "scheduled_due_date": today.isoformat(),
            "booking_date": today.isoformat(),
            "amount": "70.00",
            "direction": "credit",
            "merchant": "Operator",
            "title": "Internet",
            "transaction_type": "income",
            "category": None,
            "notes": None,
        },
    )

    assert response.status_code == 422
    db_session.expire_all()
    assert db_session.query(Transaction).count() == before


def test_transaction_cannot_be_linked_to_two_fixed_charges(client, db_session) -> None:
    today = date.today()
    transaction = _transaction(
        dedup_hash="fixed-link-conflict",
        booking_date=today,
        amount="-100.00",
    )
    db_session.add(transaction)
    db_session.commit()
    charges = [
        client.post(
            "/fixed-charges",
            json={
                "name": name,
                "amount": "100.00",
                "cadence": "monthly",
                "anchor_date": today.isoformat(),
            },
        ).json()
        for name in ("Internet", "Telefon")
    ]
    payload = {
        "transaction_ids": [transaction.id],
        "scheduled_due_date": today.isoformat(),
    }
    assert (
        client.post(
            f"/fixed-charges/{charges[0]['id']}/transactions",
            json=payload,
        ).status_code
        == 200
    )
    conflict = client.post(
        f"/fixed-charges/{charges[1]['id']}/transactions",
        json=payload,
    )
    assert conflict.status_code == 409


def test_past_unpaid_occurrence_is_overdue(db_session) -> None:
    charge = create_fixed_charge(
        db_session,
        name="Czynsz",
        amount=Decimal("2000"),
        cadence="monthly",
        anchor_date=date(2026, 1, 15),
    )

    result = list_fixed_charges(db_session, as_of=date(2026, 7, 20))

    assert result.items[0].id == charge.id
    assert result.items[0].current_due_date == date(2026, 7, 15)
    assert result.items[0].payment_status == "overdue"


def test_payment_status_is_scoped_to_schedule_occurrence(db_session) -> None:
    charge = create_fixed_charge(
        db_session,
        name="Czynsz",
        amount=Decimal("2000"),
        cadence="monthly",
        anchor_date=date(2026, 7, 15),
    )
    transaction = _transaction(
        dedup_hash="fixed-occurrence-payment",
        booking_date=date(2026, 7, 14),
        amount="-2000.00",
    )
    db_session.add(transaction)
    db_session.commit()
    link_fixed_charge_transactions(
        db_session,
        charge.id,
        transaction_ids=[transaction.id],
        scheduled_due_date=date(2026, 7, 15),
    )

    july = list_fixed_charges(db_session, as_of=date(2026, 7, 20)).items[0]
    august = list_fixed_charges(db_session, as_of=date(2026, 8, 15)).items[0]

    assert july.payment_status == "paid"
    assert july.current_paid_amount == Decimal("2000.00")
    assert august.payment_status == "pending"
    assert august.current_paid_amount == Decimal("0.00")
    assert august.linked_transaction_count == 1
