"""Tests for local profile and personal rules API."""
from __future__ import annotations

import pytest

from finance.domain.models import PersonalRule


def test_profile_settings_endpoints_are_not_exposed(client) -> None:
    assert client.get("/profile").status_code == 404
    assert client.patch("/profile", json={"base_currency": "EUR"}).status_code == 404


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


def test_personal_rule_accepts_a_custom_catalog_category(client) -> None:
    created_category = client.post("/categories", json={"name": "Pets"})
    assert created_category.status_code == 201

    response = client.post(
        "/profile/rules",
        json={"pattern": "Vet", "category": "Pets"},
    )

    assert response.status_code == 201
    assert response.json()["category"] == "pets"


@pytest.mark.parametrize(
    "field_name",
    ["pattern", "pattern_target", "priority", "active", "mode", "confidence"],
)
def test_personal_rule_patch_rejects_null_for_required_fields(
    client,
    field_name: str,
) -> None:
    created = client.post(
        "/profile/rules",
        json={"pattern": "Lidl", "category": "food"},
    )
    rule_id = created.json()["id"]

    response = client.patch(
        f"/profile/rules/{rule_id}",
        json={field_name: None},
    )

    assert response.status_code == 422
