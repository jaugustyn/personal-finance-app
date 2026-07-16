"""Tests for /categories CRUD endpoints."""
from finance.domain.models import CategoryDef


def test_list_seeds_system_categories(client, db_session) -> None:
    # Empty table on first call.
    assert db_session.query(CategoryDef).count() == 0
    r = client.get("/categories")
    assert r.status_code == 200
    body = r.json()
    names = {c["name"] for c in body}
    # All built-ins.
    assert {"food", "transport", "subscriptions", "health",
            "entertainment", "housing", "savings", "shopping", "other"} <= names
    # All marked as system.
    assert all(c["is_system"] for c in body)


def test_list_includes_user_categories_after_create(client) -> None:
    r = client.post("/categories", json={"name": "Pets", "color": "#ff00ff"})
    assert r.status_code == 201
    assert r.json()["name"] == "pets"
    assert r.json()["is_system"] is False

    r2 = client.get("/categories")
    body = r2.json()
    pets = next(c for c in body if c["name"] == "pets")
    assert pets["color"] == "#ff00ff"


def test_create_duplicate_returns_409(client) -> None:
    client.post("/categories", json={"name": "Hobby"})
    r = client.post("/categories", json={"name": "hobby"})  # case-insensitive
    assert r.status_code == 409


def test_delete_user_category(client) -> None:
    r = client.post("/categories", json={"name": "Travel"})
    cid = r.json()["id"]
    r2 = client.delete(f"/categories/{cid}")
    assert r2.status_code == 204
    listing = client.get("/categories").json()
    assert all(c["name"] != "travel" for c in listing)


def test_delete_used_user_category_is_blocked(client, db_session) -> None:
    from datetime import date
    from decimal import Decimal

    from finance.domain.models import Transaction

    created = client.post("/categories", json={"name": "Education"}).json()
    db_session.add(
        Transaction(
            booking_date=date(2026, 4, 1),
            amount=Decimal("-10"),
            currency="PLN",
            direction="debit",
            merchant="A",
            title="x",
            category="education",
            source="pekao",
            dedup_hash="used-custom-category",
        )
    )
    db_session.commit()

    response = client.delete(f"/categories/{created['id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "category_in_use",
        "message": "Category is in use and cannot be deleted.",
        "transaction_count": 1,
        "rule_count": 0,
        "subcategory_count": 0,
    }
    assert db_session.get(CategoryDef, created["id"]) is not None


def test_delete_system_category_is_forbidden(client) -> None:
    listing = client.get("/categories").json()
    food = next(c for c in listing if c["name"] == "food")
    r = client.delete(f"/categories/{food['id']}")
    assert r.status_code == 409


def test_patch_category_color(client) -> None:
    listing = client.get("/categories").json()
    food = next(c for c in listing if c["name"] == "food")
    r = client.patch(f"/categories/{food['id']}", json={"color": "#123456"})
    assert r.status_code == 200
    assert r.json()["color"] == "#123456"


def test_usage_count_reflects_transactions(client, db_session) -> None:
    from datetime import date
    from decimal import Decimal

    from finance.domain.models import Transaction

    db_session.add_all([
        Transaction(
            booking_date=date(2026, 4, 1), amount=Decimal("-10"),
            currency="PLN", direction="debit", merchant="A", title="x",
            category="food", source="pekao", dedup_hash=f"h-{i}",
        )
        for i in range(3)
    ])
    db_session.commit()

    listing = client.get("/categories").json()
    food = next(c for c in listing if c["name"] == "food")
    assert food["usage_count"] == 3
