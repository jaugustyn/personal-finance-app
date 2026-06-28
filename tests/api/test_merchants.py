from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.models import Transaction


def _tx(
    db_session,
    *,
    merchant: str,
    amount: Decimal,
    dedup_hash: str,
    title: str = "",
) -> Transaction:
    tx = Transaction(
        booking_date=date(2026, 4, 15),
        amount=amount,
        currency="PLN",
        direction="debit",
        merchant=merchant,
        title=title,
        category="food",
        source="pekao",
        dedup_hash=dedup_hash,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


def test_merchant_candidates_group_variants(client, db_session) -> None:
    _tx(db_session, merchant="BIEDRONKA 1234 WARSZAWA", amount=Decimal("-10"), dedup_hash="m1")
    _tx(db_session, merchant="Biedronka PayU", amount=Decimal("-20"), dedup_hash="m2")
    _tx(db_session, merchant="Other", amount=Decimal("-30"), dedup_hash="m3")

    response = client.get("/merchants/candidates")

    assert response.status_code == 200
    body = response.json()
    biedronka = next(row for row in body if row["canonical_key"] == "biedronka")
    assert biedronka["count"] == 2
    assert set(biedronka["aliases"]) == {
        "biedronka 1234 warszawa",
        "biedronka payu",
    }
    assert {row["alias_key"] for row in biedronka["variants"]} == {
        "biedronka 1234 warszawa",
        "biedronka payu",
    }
    assert sum(row["count"] for row in biedronka["variants"]) == 2
    assert Decimal(str(sum(Decimal(row["total_debit"]) for row in biedronka["variants"]))) == Decimal("30")


def test_merchant_candidates_use_title_for_generic_bank_merchant(client, db_session) -> None:
    _tx(
        db_session,
        merchant="CARD PAYMENT",
        title="CARD PAYMENT NETFLIX.COM",
        amount=Decimal("-49.99"),
        dedup_hash="generic-netflix-merchant",
    )
    _tx(
        db_session,
        merchant="CARD PAYMENT",
        title="CARD PAYMENT NETFLIX AMSTERDAM",
        amount=Decimal("-49.99"),
        dedup_hash="generic-netflix-title",
    )

    response = client.get("/merchants/candidates")

    assert response.status_code == 200
    netflix = next(row for row in response.json() if row["canonical_key"] == "netflix")
    assert netflix["count"] == 2
    assert {row["alias_key"] for row in netflix["variants"]} == {
        "card payment netflix com",
        "card payment netflix amsterdam",
    }


def test_merchant_alias_suggestions_search_existing_transaction_variants(
    client,
    db_session,
) -> None:
    _tx(
        db_session,
        merchant="CARD PAYMENT",
        title="CARD PAYMENT NETFLIX.COM",
        amount=Decimal("-49.99"),
        dedup_hash="suggest-netflix-1",
    )
    _tx(
        db_session,
        merchant="NETFLIX.COM AMSTERDAM",
        amount=Decimal("-59.99"),
        dedup_hash="suggest-netflix-2",
    )

    response = client.get("/merchants/suggestions", params={"q": "net"})

    assert response.status_code == 200
    rows = response.json()
    assert {row["alias_key"] for row in rows} >= {
        "card payment netflix com",
        "netflix com amsterdam",
    }
    first = next(row for row in rows if row["alias_key"] == "card payment netflix com")
    assert first["count"] == 1
    assert first["canonical_key"] == "netflix"


def test_merchant_alias_suggestions_skip_saved_aliases(client, db_session) -> None:
    _tx(
        db_session,
        merchant="NETFLIX.COM AMSTERDAM",
        amount=Decimal("-59.99"),
        dedup_hash="suggest-saved-netflix",
    )
    created = client.post(
        "/merchants/aliases",
        json={"canonical_label": "Netflix", "aliases": ["NETFLIX.COM AMSTERDAM"]},
    )
    assert created.status_code == 201

    response = client.get("/merchants/suggestions", params={"q": "netflix"})

    assert response.status_code == 200
    assert all(row["alias_key"] != "netflix com amsterdam" for row in response.json())


def test_merchant_alias_crud(client) -> None:
    payload = {
        "canonical_label": "Biedronka",
        "aliases": ["BIEDRONKA 1234 WARSZAWA", "Biedronka PayU"],
    }

    created = client.post("/merchants/aliases", json=payload)

    assert created.status_code == 201
    rows = created.json()
    assert len(rows) == 2
    assert {row["canonical_key"] for row in rows} == {"biedronka"}

    listed = client.get("/merchants/aliases")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    deleted = client.delete(f"/merchants/aliases/{rows[0]['id']}")
    assert deleted.status_code == 204
    assert len(client.get("/merchants/aliases").json()) == 1


def test_merchant_alias_upsert_moves_alias_between_groups(client) -> None:
    created = client.post(
        "/merchants/aliases",
        json={"canonical_label": "Biedronka", "aliases": ["Biedronka PayU"]},
    )
    assert created.status_code == 201
    alias_id = created.json()[0]["id"]

    moved = client.post(
        "/merchants/aliases",
        json={
            "canonical_key": "groceries",
            "canonical_label": "Groceries",
            "aliases": ["Biedronka PayU"],
        },
    )

    assert moved.status_code == 201
    row = moved.json()[0]
    assert row["id"] == alias_id
    assert row["canonical_key"] == "groceries"
    assert row["canonical_label"] == "Groceries"


def test_saved_merchant_aliases_disappear_from_candidates(client, db_session) -> None:
    _tx(db_session, merchant="BIEDRONKA 1234 WARSZAWA", amount=Decimal("-10"), dedup_hash="saved-m1")
    _tx(db_session, merchant="Biedronka PayU", amount=Decimal("-20"), dedup_hash="saved-m2")

    before = client.get("/merchants/candidates")
    assert before.status_code == 200
    assert any(row["canonical_key"] == "biedronka" for row in before.json())

    created = client.post(
        "/merchants/aliases",
        json={
            "canonical_key": "biedronka",
            "canonical_label": "Biedronka",
            "aliases": ["BIEDRONKA 1234 WARSZAWA", "Biedronka PayU"],
        },
    )
    assert created.status_code == 201

    after = client.get("/merchants/candidates")
    assert after.status_code == 200
    assert all(row["canonical_key"] != "biedronka" for row in after.json())


def test_patch_merchant_alias_group_label_changes_display_only(client) -> None:
    created = client.post(
        "/merchants/aliases",
        json={
            "canonical_label": "Biedronka",
            "aliases": ["BIEDRONKA 1234 WARSZAWA", "Biedronka PayU"],
        },
    )
    assert created.status_code == 201

    patched = client.patch(
        "/merchants/aliases/group-label",
        json={"canonical_key": "biedronka", "canonical_label": "Biedronka sklepy"},
    )

    assert patched.status_code == 200
    rows = patched.json()
    assert len(rows) == 2
    assert {row["canonical_key"] for row in rows} == {"biedronka"}
    assert {row["canonical_label"] for row in rows} == {"Biedronka sklepy"}


def test_alias_changes_top_merchants_without_updating_transactions(
    client,
    db_session,
) -> None:
    _tx(db_session, merchant="KIK WARSZAWA", amount=Decimal("-10"), dedup_hash="alias-kik")
    _tx(db_session, merchant="TEDI WARSZAWA", amount=Decimal("-20"), dedup_hash="alias-tedi")

    before = client.get("/stats/top-merchants?months=120&limit=5")
    assert before.status_code == 200
    assert {row["merchant"] for row in before.json()} >= {"KIK WARSZAWA", "TEDI WARSZAWA"}

    response = client.post(
        "/merchants/aliases",
        json={
            "canonical_label": "Discount stores",
            "aliases": ["KIK WARSZAWA", "TEDI WARSZAWA"],
        },
    )
    assert response.status_code == 201

    after = client.get("/stats/top-merchants?months=120&limit=5")
    rows = after.json()
    merged = next(row for row in rows if row["merchant"] == "Discount stores")
    assert Decimal(merged["amount"]) == Decimal("30.00")
    assert merged["count"] == 2

    original = db_session.query(Transaction).filter_by(dedup_hash="alias-kik").one()
    assert original.merchant == "KIK WARSZAWA"
