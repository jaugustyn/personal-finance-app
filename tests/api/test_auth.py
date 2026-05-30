"""Auth + health smoke tests."""
import os
from importlib import reload

import pytest
from fastapi.testclient import TestClient


def _make_client(env: dict[str, str]) -> TestClient:
    for k, v in env.items():
        os.environ[k] = v
    # Reset settings cache + reload modules that read settings at import.
    from finance import config
    config.get_settings.cache_clear()

    from apps.api import main as api_main
    reload(api_main)
    return TestClient(api_main.app, raise_server_exceptions=False)


def test_health_public_no_auth():
    client = _make_client({"AUTH_USERNAME": "", "AUTH_PASSWORD": ""})
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["auth_enabled"] is False
    assert "checks" in body


def test_protected_endpoint_requires_auth_when_enabled():
    client = _make_client({"AUTH_USERNAME": "alice", "AUTH_PASSWORD": "secret"})
    # /health remains public
    assert client.get("/health").status_code == 200
    assert client.get("/health").json()["auth_enabled"] is True

    # Protected route without credentials -> 401
    r = client.get("/transactions")
    assert r.status_code == 401

    # Wrong credentials -> 401
    r = client.get("/transactions", auth=("alice", "wrong"))
    assert r.status_code == 401

    # Correct credentials -> not 401 (may be 500 since DB may be missing in test
    # env, but auth itself passed).
    r = client.get("/transactions", auth=("alice", "secret"))
    assert r.status_code != 401


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for k in ("AUTH_USERNAME", "AUTH_PASSWORD"):
        os.environ.pop(k, None)
    from finance import config
    config.get_settings.cache_clear()
