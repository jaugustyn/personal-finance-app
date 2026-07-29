"""Tests for local profile and personal rules API."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from finance.domain.models import PersonalRule, UserProfile


def test_profile_settings_endpoints_are_not_exposed(client) -> None:
    assert client.get("/profile").status_code == 404
    assert client.patch("/profile", json={"base_currency": "EUR"}).status_code == 404


def test_assistant_settings_can_disable_local_model(
    client,
    db_session,
    monkeypatch,
) -> None:
    from apps.api.routers import profile as profile_router

    monkeypatch.setattr(
        profile_router,
        "get_settings",
        lambda: SimpleNamespace(llm_enabled=True, ollama_model="default:latest"),
    )
    monkeypatch.setattr(
        profile_router,
        "ollama_models",
        lambda: ["default:latest", "small:latest"],
    )

    initial = client.get("/profile/assistant")
    assert initial.status_code == 200
    assert initial.json() == {
        "user_enabled": True,
        "configuration_enabled": True,
        "ollama_available": True,
        "mode": "hybrid",
        "model": "default:latest",
        "available_models": ["default:latest", "small:latest"],
    }

    updated = client.put("/profile/assistant", json={"enabled": False})
    assert updated.status_code == 200
    assert updated.json() == {
        "user_enabled": False,
        "configuration_enabled": True,
        "ollama_available": False,
        "mode": "deterministic",
        "model": "default:latest",
        "available_models": [],
    }
    assert db_session.get(UserProfile, 1).assistant_llm_enabled is False


def test_assistant_settings_respect_server_kill_switch(
    client,
    monkeypatch,
) -> None:
    from apps.api.routers import profile as profile_router

    monkeypatch.setattr(
        profile_router,
        "get_settings",
        lambda: SimpleNamespace(llm_enabled=False, ollama_model="default:latest"),
    )

    def unexpected_probe() -> list[str]:
        raise AssertionError("Ollama must not be probed when disabled by configuration")

    monkeypatch.setattr(profile_router, "ollama_models", unexpected_probe)

    response = client.get("/profile/assistant")
    assert response.status_code == 200
    assert response.json() == {
        "user_enabled": True,
        "configuration_enabled": False,
        "ollama_available": False,
        "mode": "deterministic",
        "model": "default:latest",
        "available_models": [],
    }


def test_assistant_settings_can_select_an_installed_model(
    client,
    db_session,
    monkeypatch,
) -> None:
    from apps.api.routers import profile as profile_router

    monkeypatch.setattr(
        profile_router,
        "get_settings",
        lambda: SimpleNamespace(llm_enabled=True, ollama_model="default:latest"),
    )
    monkeypatch.setattr(
        profile_router,
        "ollama_models",
        lambda: ["default:latest", "qwen:7b"],
    )

    response = client.put(
        "/profile/assistant",
        json={"enabled": True, "model": "qwen:7b"},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "qwen:7b"
    assert response.json()["ollama_available"] is True
    assert db_session.get(UserProfile, 1).assistant_llm_model == "qwen:7b"


def test_assistant_settings_reject_uninstalled_model(client, monkeypatch) -> None:
    from apps.api.routers import profile as profile_router

    monkeypatch.setattr(
        profile_router,
        "get_settings",
        lambda: SimpleNamespace(llm_enabled=True, ollama_model="default:latest"),
    )
    monkeypatch.setattr(
        profile_router,
        "ollama_models",
        lambda: ["default:latest"],
    )

    response = client.put(
        "/profile/assistant",
        json={"enabled": True, "model": "missing:latest"},
    )

    assert response.status_code == 422


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
