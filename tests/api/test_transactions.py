"""Tests for /transactions endpoints (list, summary, PATCH category)."""
from datetime import date
from decimal import Decimal

from finance.domain.models import Transaction


def _seed(session, **overrides) -> Transaction:
    tx = Transaction(
        booking_date=date(2026, 4, 15),
        amount=Decimal("-50.00"),
        currency="PLN",
        direction="debit",
        merchant="Carrefour",
        title="Zakupy",
        category="food",
        category_predicted=None,
        category_confidence=None,
        source="pekao",
        dedup_hash="hash-1",
    )
    for k, v in overrides.items():
        setattr(tx, k, v)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_list_transactions_empty(client) -> None:
    r = client.get("/transactions")
    assert r.status_code == 200
    assert r.json() == []


def test_list_transactions_returns_seeded(client, db_session) -> None:
    _seed(db_session)
    r = client.get("/transactions")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["merchant"] == "Carrefour"
    assert body[0]["category"] == "food"
    assert body[0]["category_suggestion_rejected"] is False
    assert body[0]["transaction_type"] == "purchase"


def test_list_transactions_date_filter(client, db_session) -> None:
    _seed(db_session, booking_date=date(2026, 4, 1), dedup_hash="h-april")
    _seed(db_session, booking_date=date(2026, 1, 1), dedup_hash="h-jan")
    r = client.get("/transactions?date_from=2026-03-01")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["booking_date"] == "2026-04-01"


def test_list_transactions_filters_suggestions_and_type(client, db_session) -> None:
    suggested = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.91,
        category_predicted_source="model",
        dedup_hash="h-suggested",
    )
    _seed(db_session, category=None, category_predicted=None, dedup_hash="h-empty")
    _seed(
        db_session,
        category=None,
        category_predicted="transport",
        category_confidence=0.40,
        category_predicted_source="model",
        dedup_hash="h-low",
    )
    _seed(
        db_session,
        category=None,
        category_predicted="other",
        category_suggestion_rejected=True,
        transaction_type="person_transfer",
        dedup_hash="h-rejected",
    )

    r = client.get("/transactions?category_state=suggested&min_confidence=0.75")

    assert r.status_code == 200
    assert [row["id"] for row in r.json()] == [suggested.id]

    r2 = client.get("/transactions?category_state=rejected&transaction_type=person_transfer")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["category_suggestion_rejected"] is True


def test_export_csv_streams_attachment(client, db_session) -> None:
    _seed(db_session)
    r = client.get("/transactions/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.text
    lines = text.strip().splitlines()
    assert lines[0].startswith("id,booking_date,amount,currency,direction,")
    assert len(lines) == 2
    assert "Carrefour" in lines[1]


def test_export_csv_escapes_formula_injection(client, db_session) -> None:
    """Cells starting with =/+/-/@ must be prefixed with ' to neutralise
    spreadsheet formula injection (CWE-1236)."""
    _seed(
        db_session,
        merchant="=cmd|'/c calc'!A1",
        title="+1+1",
        dedup_hash="h-injection",
    )
    r = client.get("/transactions/export.csv")
    assert r.status_code == 200
    text = r.text
    # Leading "'" is inserted by _safe(); the raw "=cmd" / "+1+1" cells must
    # not appear unprefixed.
    assert "'=cmd" in text
    assert "'+1+1" in text
    assert ",=cmd" not in text
    assert ",+1+1" not in text


def test_patch_category_updates(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-patch")
    r = client.patch(f"/transactions/{tx.id}/category", json={"category": "transport"})
    assert r.status_code == 200
    assert r.json()["category"] == "transport"
    assert r.json()["category_source"] == "manual"

    # Persistence check via fresh GET
    r2 = client.get("/transactions")
    assert r2.json()[0]["category"] == "transport"


def test_patch_category_can_remember_merchant_rule(client, db_session) -> None:
    tx = _seed(db_session, category=None, merchant="Lidl", dedup_hash="h-remember")

    r = client.patch(
        f"/transactions/{tx.id}/category",
        json={"category": "food", "remember_rule": True},
    )

    assert r.status_code == 200
    rules = client.get("/profile/rules").json()
    assert len(rules) == 1
    assert rules[0]["pattern"] == "Lidl"
    assert rules[0]["category"] == "food"
    assert rules[0]["mode"] == "suggest_only"


def test_patch_category_clears_with_null(client, db_session) -> None:
    tx = _seed(db_session, category="food", dedup_hash="h-clear")
    r = client.patch(f"/transactions/{tx.id}/category", json={"category": None})
    assert r.status_code == 200
    assert r.json()["category"] is None


def test_patch_category_404_on_missing(client) -> None:
    r = client.patch("/transactions/9999/category", json={"category": "food"})
    assert r.status_code == 404


def test_summary_by_category(client, db_session) -> None:
    _seed(db_session, category="food", amount=Decimal("-30.00"), dedup_hash="s1")
    _seed(
        db_session,
        category="food",
        amount=Decimal("-20.00"),
        dedup_hash="s2",
        booking_date=date(2026, 4, 16),
    )
    _seed(
        db_session,
        category="transport",
        amount=Decimal("-15.00"),
        dedup_hash="s3",
        booking_date=date(2026, 4, 17),
    )
    r = client.get("/transactions/summary/by-category")
    assert r.status_code == 200
    body = r.json()
    cats = {row["category"]: row for row in body}
    assert "food" in cats and "transport" in cats
    assert cats["food"]["count"] == 2
    assert cats["transport"]["count"] == 1


def test_accept_suggestions_endpoint(client, db_session) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.88,
        category_predicted_source="model",
        dedup_hash="h-suggest",
    )

    r = client.post(
        "/transactions/bulk/accept-suggestions",
        json={"ids": [tx.id], "min_confidence": 0.75},
    )

    assert r.status_code == 200
    assert r.json()["affected"] == 1
    db_session.refresh(tx)
    assert tx.category == "food"
    assert tx.category_source == "model"


def test_reject_suggestions_endpoint(client, db_session) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.88,
        category_predicted_source="model",
        dedup_hash="h-reject",
    )

    r = client.post("/transactions/bulk/reject-suggestions", json={"ids": [tx.id]})

    assert r.status_code == 200
    assert r.json()["affected"] == 1
    db_session.refresh(tx)
    assert tx.category is None
    assert tx.category_predicted is None
    assert tx.category_confidence is None
    assert tx.category_predicted_source is None
    assert tx.category_suggestion_rejected is True
