"""API coverage for the optional single-user application lock."""
from __future__ import annotations

import pytest

from finance.domain.models import UserProfile
from finance.security import app_lock


@pytest.fixture(autouse=True)
def _isolated_app_lock(monkeypatch):
    app_lock.reset_runtime_state()
    monkeypatch.setattr(app_lock, "_SCRYPT_N", 2**10)
    yield
    app_lock.reset_runtime_state()


def _setup(client, *, code: str = "123456", timeout: int = 15):
    return client.post(
        "/app-lock/setup",
        json={"code": code, "timeout_minutes": timeout},
    )


def test_disabled_lock_keeps_existing_api_behavior(client):
    status = client.get("/app-lock/status")
    assert status.status_code == 200
    assert status.json() == {
        "enabled": False,
        "locked": False,
        "timeout_minutes": 15,
    }
    assert client.get("/profile/rules").status_code == 200


def test_status_and_unlocked_dependency_do_not_create_profile(client, db_session):
    assert db_session.get(UserProfile, 1) is None

    assert client.get("/app-lock/status").status_code == 200
    assert client.get("/profile/rules").status_code == 200

    db_session.expire_all()
    assert db_session.get(UserProfile, 1) is None


def test_setup_hashes_code_sets_cookie_and_unlocks(client, db_session):
    response = _setup(client, code="private-code", timeout=30)

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "locked": False,
        "timeout_minutes": 30,
    }
    cookie = response.headers["set-cookie"]
    assert "finance_app_lock_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie
    profile = db_session.get(UserProfile, 1)
    assert profile is not None
    assert profile.app_lock_secret_hash != "private-code"
    assert "private-code" not in (profile.app_lock_secret_hash or "")
    assert client.get("/profile/rules").status_code == 200


def test_missing_expired_or_damaged_runtime_session_returns_423(client):
    assert _setup(client).status_code == 200
    app_lock.revoke_all_sessions()

    response = client.get("/profile/rules")
    assert response.status_code == 423
    assert response.json()["detail"]["code"] == "app_locked"
    assert client.get("/app-lock/status").json()["locked"] is True


def test_unlock_rejects_wrong_code_and_resets_failures_after_success(client):
    assert _setup(client, code="correct-code").status_code == 200
    app_lock.revoke_all_sessions()

    wrong = client.post("/app-lock/unlock", json={"code": "wrong-code"})
    assert wrong.status_code == 401
    assert wrong.json()["detail"]["code"] == "invalid_lock_code"

    unlocked = client.post(
        "/app-lock/unlock", json={"code": "correct-code"}
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["locked"] is False
    assert client.get("/profile/rules").status_code == 200


def test_fifth_failed_unlock_is_rate_limited(client):
    assert _setup(client, code="correct-code").status_code == 200
    app_lock.revoke_all_sessions()

    for _ in range(4):
        assert (
            client.post("/app-lock/unlock", json={"code": "wrong-code"}).status_code
            == 401
        )
    limited = client.post("/app-lock/unlock", json={"code": "wrong-code"})
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "app_lock_rate_limited"
    assert int(limited.headers["retry-after"]) > 0


def test_manual_lock_and_activity_endpoint(client):
    assert _setup(client).status_code == 200
    assert client.post("/app-lock/activity").status_code == 204

    locked = client.post("/app-lock/lock")
    assert locked.status_code == 204
    assert "finance_app_lock_session=" in locked.headers["set-cookie"]
    assert client.get("/profile/rules").status_code == 423


def test_change_code_invalidates_other_sessions_and_old_code(client):
    assert _setup(client, code="old-code").status_code == 200
    second_token = app_lock.create_session()

    changed = client.put(
        "/app-lock/settings",
        json={
            "enabled": True,
            "current_code": "old-code",
            "new_code": "new-code",
            "timeout_minutes": 60,
        },
    )
    assert changed.status_code == 200
    assert changed.json()["timeout_minutes"] == 60
    assert not app_lock.session_is_active(second_token, 60)

    app_lock.revoke_all_sessions()
    assert (
        client.post("/app-lock/unlock", json={"code": "old-code"}).status_code
        == 401
    )
    assert (
        client.post("/app-lock/unlock", json={"code": "new-code"}).status_code
        == 200
    )


def test_disable_removes_session_requirement(client):
    assert _setup(client, code="current-code").status_code == 200
    disabled = client.put(
        "/app-lock/settings",
        json={
            "enabled": False,
            "current_code": "current-code",
            "timeout_minutes": 15,
        },
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert client.get("/profile/rules").status_code == 200


def test_session_timeout_and_touch_are_server_side(monkeypatch):
    now = 100.0
    monkeypatch.setattr(app_lock, "_now", lambda: now)
    token = app_lock.create_session()

    now = 100.0 + 4 * 60
    assert app_lock.session_is_active(token, 5, touch=True)
    now = 100.0 + 8 * 60
    assert app_lock.session_is_active(token, 5, touch=False)
    now = 100.0 + 9 * 60
    assert not app_lock.session_is_active(token, 5, touch=False)


def test_background_api_requests_do_not_extend_idle_session(client, monkeypatch):
    now = 100.0
    monkeypatch.setattr(app_lock, "_now", lambda: now)
    assert _setup(client, timeout=5).status_code == 200

    now += 4 * 60
    assert client.get("/profile/rules").status_code == 200

    now += 2 * 60
    assert client.get("/profile/rules").status_code == 423


def test_status_check_does_not_extend_idle_session(client, monkeypatch):
    now = 100.0
    monkeypatch.setattr(app_lock, "_now", lambda: now)
    assert _setup(client, timeout=5).status_code == 200

    now += 4 * 60
    assert client.get("/app-lock/status").json()["locked"] is False

    now += 2 * 60
    assert client.get("/app-lock/status").json()["locked"] is True
    assert client.get("/profile/rules").status_code == 423


def test_activity_endpoint_extends_idle_session(client, monkeypatch):
    now = 100.0
    monkeypatch.setattr(app_lock, "_now", lambda: now)
    assert _setup(client, timeout=5).status_code == 200

    now += 4 * 60
    assert client.post("/app-lock/activity").status_code == 204

    now += 4 * 60
    assert client.get("/profile/rules").status_code == 200
