"""Tests for transaction bulk operations, groups, delete, transfer filter."""
from datetime import date
from decimal import Decimal

from finance.domain.models import Import, MlFeedbackEvent, Transaction


def _tx(session, **overrides) -> Transaction:
    base = dict(
        booking_date=date(2026, 4, 1),
        amount=Decimal("-10.00"),
        currency="PLN",
        direction="debit",
        merchant="Carrefour",
        title="Zakupy",
        category=None,
        source="pekao",
        dedup_hash=f"h-{id(overrides)}-{overrides.get('dedup_hash','')}",
    )
    base.update(overrides)
    tx = Transaction(**base)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_delete_transaction(client, db_session) -> None:
    tx = _tx(db_session, dedup_hash="d1")
    tx_id = tx.id
    r = client.delete(f"/transactions/{tx.id}")
    assert r.status_code == 204
    db_session.expire_all()
    assert db_session.get(Transaction, tx_id) is None


def test_delete_transaction_detaches_ml_feedback(client, db_session) -> None:
    tx = _tx(db_session, dedup_hash="d-feedback")
    tx_id = tx.id
    event = MlFeedbackEvent(
        transaction_id=tx_id,
        event_type="anomaly_relevant",
        entity_type="anomaly_merchant",
        entity_key=tx.merchant,
    )
    db_session.add(event)
    db_session.commit()
    event_id = event.id

    r = client.delete(f"/transactions/{tx_id}")

    assert r.status_code == 204
    db_session.expire_all()
    assert db_session.get(Transaction, tx_id) is None
    stored_event = db_session.get(MlFeedbackEvent, event_id)
    assert stored_event is not None
    assert stored_event.transaction_id is None


def test_bulk_delete(client, db_session) -> None:
    a = _tx(db_session, dedup_hash="bd1")
    b = _tx(db_session, dedup_hash="bd2")
    c = _tx(db_session, dedup_hash="bd3")
    r = client.post("/transactions/bulk/delete", json={"ids": [a.id, b.id]})
    assert r.status_code == 200
    assert r.json()["affected"] == 2
    assert db_session.get(Transaction, c.id) is not None


def test_bulk_categorize_by_ids(client, db_session) -> None:
    a = _tx(db_session, dedup_hash="bc1")
    b = _tx(db_session, dedup_hash="bc2")
    r = client.post(
        "/transactions/bulk/categorize",
        json={"ids": [a.id, b.id], "category": "food"},
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 2
    db_session.refresh(a)
    db_session.refresh(b)
    assert a.category == "food"
    assert b.category == "food"


def test_bulk_categorize_by_merchant(client, db_session) -> None:
    _tx(db_session, merchant="Lidl", dedup_hash="m1")
    _tx(db_session, merchant="Lidl", dedup_hash="m2")
    _tx(db_session, merchant="Other", dedup_hash="m3")
    r = client.post(
        "/transactions/bulk/categorize",
        json={"merchant": "Lidl", "category": "food"},
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 2


def test_bulk_categorize_requires_selection(client) -> None:
    r = client.post("/transactions/bulk/categorize", json={"category": "food"})
    assert r.status_code == 422


def test_groups_returns_uncategorized_merchants(client, db_session) -> None:
    _tx(db_session, merchant="Biedronka", dedup_hash="g1")
    _tx(db_session, merchant="Biedronka", dedup_hash="g2")
    _tx(db_session, merchant="Lidl", category="food", dedup_hash="g3")
    _tx(db_session, merchant="Lidl", category="food", dedup_hash="g4")
    r = client.get("/transactions/groups?only_uncategorized=true&min_count=2")
    assert r.status_code == 200
    body = r.json()
    merchants = {g["merchant"] for g in body}
    assert "Biedronka" in merchants
    assert "Lidl" not in merchants


def test_groups_min_count_filter(client, db_session) -> None:
    _tx(db_session, merchant="OneOff", dedup_hash="o1")
    _tx(db_session, merchant="Frequent", dedup_hash="f1")
    _tx(db_session, merchant="Frequent", dedup_hash="f2")
    r = client.get("/transactions/groups?min_count=2&only_uncategorized=true")
    body = r.json()
    merchants = {g["merchant"] for g in body}
    assert "Frequent" in merchants
    assert "OneOff" not in merchants


def test_list_filter_include_transfers(client, db_session) -> None:
    _tx(db_session, dedup_hash="nt1", is_transfer=False)
    _tx(db_session, dedup_hash="t1", is_transfer=True, merchant="Self")
    r = client.get("/transactions?include_transfers=false")
    body = r.json()
    assert len(body) == 1
    assert body[0]["is_transfer"] is False


def test_list_filter_by_import_id(client, db_session) -> None:
    imp = Import(source="pekao", filename="x.csv", total_rows=2)
    db_session.add(imp)
    db_session.commit()
    db_session.refresh(imp)
    _tx(db_session, dedup_hash="i1", import_id=imp.id)
    _tx(db_session, dedup_hash="i2")
    r = client.get(f"/transactions?import_id={imp.id}")
    body = r.json()
    assert len(body) == 1
    assert body[0]["import_id"] == imp.id


def test_list_imports_endpoint(client, db_session) -> None:
    db_session.add(Import(source="pekao", filename="a.csv", total_rows=5, inserted=3, duplicates=2))
    db_session.add(Import(source="revolut", filename="b.csv", total_rows=10, inserted=10))
    db_session.commit()
    r = client.get("/imports")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    filenames = {i["filename"] for i in body}
    assert filenames == {"a.csv", "b.csv"}


def test_delete_import_cascades(client, db_session) -> None:
    imp = Import(source="pekao", filename="del.csv", total_rows=2)
    db_session.add(imp)
    db_session.commit()
    db_session.refresh(imp)
    _tx(db_session, dedup_hash="di1", import_id=imp.id)
    _tx(db_session, dedup_hash="di2", import_id=imp.id)
    _tx(db_session, dedup_hash="di3")  # unrelated

    r = client.delete(f"/imports/{imp.id}")
    assert r.status_code == 200
    assert r.json()["deleted_transactions"] == 2
    imp_id = imp.id
    db_session.expire_all()
    # Unrelated tx is still there.
    remaining = db_session.query(Transaction).count()
    assert remaining == 1
    assert db_session.query(Import).filter_by(id=imp_id).first() is None


def test_delete_import_not_found(client) -> None:
    r = client.delete("/imports/9999")
    assert r.status_code == 404
