"""Tests for local profile and personal rules API."""
from __future__ import annotations

from decimal import Decimal

from finance.domain.models import PersonalRule


def test_profile_get_creates_singleton(client) -> None:
    response = client.get("/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["base_currency"] == "PLN"
    assert body["category_limits"] == {}


def test_profile_patch_updates_operational_fields(client) -> None:
    response = client.patch(
        "/profile",
        json={
            "base_currency": "eur",
            "salary_day": 10,
            "monthly_savings_goal": "1200.00",
            "category_limits": {"food": 900.0, "unknown": 999.0},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["base_currency"] == "EUR"
    assert body["salary_day"] == 10
    assert Decimal(body["monthly_savings_goal"]) == Decimal("1200.00")
    assert body["category_limits"] == {"food": 900.0}


def test_personal_rules_crud(client, db_session) -> None:
    create = client.post(
        "/profile/rules",
        json={
            "pattern": "Lidl",
            "pattern_target": "merchant",
            "category": "food",
            "priority": 20,
            "mode": "suggest_only",
        },
    )
    assert create.status_code == 201
    rule_id = create.json()["id"]
    assert create.json()["pattern_norm"] == "lidl"

    listed = client.get("/profile/rules")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [rule_id]

    patched = client.patch(
        f"/profile/rules/{rule_id}",
        json={"active": False, "mode": "auto_apply", "confidence": 0.99},
    )
    assert patched.status_code == 200
    assert patched.json()["active"] is False
    assert patched.json()["mode"] == "auto_apply"

    deleted = client.delete(f"/profile/rules/{rule_id}")
    assert deleted.status_code == 204
    assert db_session.get(PersonalRule, rule_id) is None


def test_personal_rule_rejects_invalid_enum_values(client) -> None:
    response = client.post(
        "/profile/rules",
        json={
            "pattern": "Lidl",
            "pattern_target": "merchant",
            "category": "not-a-category",
            "transaction_type": "not-a-type",
        },
    )

    assert response.status_code == 422
