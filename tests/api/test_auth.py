"""Auth + health smoke tests."""
import os
from importlib import reload

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


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
    assert r.json() == {"status": "ok"}


def test_protected_endpoint_requires_auth_when_enabled():
    client = _make_client({"AUTH_USERNAME": "alice", "AUTH_PASSWORD": "secret"})
    # /health remains public
    assert client.get("/health").status_code == 200

    # Protected route without credentials -> 401
    r = client.get("/transactions")
    assert r.status_code == 401
    assert client.get("/app-lock/status").status_code == 401

    # Wrong credentials -> 401
    r = client.get("/transactions", auth=("alice", "wrong"))
    assert r.status_code == 401

    # Correct credentials -> not 401 (may be 500 since DB may be missing in test
    # env, but auth itself passed).
    r = client.get("/transactions", auth=("alice", "secret"))
    assert r.status_code != 401
    assert client.get("/app-lock/status", auth=("alice", "secret")).status_code != 401


@pytest.mark.parametrize(
    ("username", "password"),
    [("alice", ""), ("", "secret")],
)
def test_partial_basic_auth_configuration_stops_startup(username, password):
    with pytest.raises(ValidationError, match="must both be configured"):
        _make_client({"AUTH_USERNAME": username, "AUTH_PASSWORD": password})


def test_api_documentation_is_disabled_by_default():
    client = _make_client(
        {
            "AUTH_USERNAME": "",
            "AUTH_PASSWORD": "",
            "API_DOCS_ENABLED": "false",
        }
    )
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for k in ("AUTH_USERNAME", "AUTH_PASSWORD"):
        os.environ.pop(k, None)
    os.environ["API_DOCS_ENABLED"] = "true"
    from finance import config
    config.get_settings.cache_clear()
