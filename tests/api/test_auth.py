"""Auth + health smoke tests."""
from importlib import reload

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api import main as api_main
from finance.config import get_settings


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    def configure(**values: str) -> None:
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    configure(AUTH_USERNAME="", AUTH_PASSWORD="")
    yield configure
    get_settings.cache_clear()


def test_health_public_no_auth(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_protected_endpoint_requires_auth_when_enabled(client, auth_settings):
    auth_settings(AUTH_USERNAME="alice", AUTH_PASSWORD="secret")
    # /health remains public
    assert client.get("/health").status_code == 200

    # Protected route without credentials -> 401
    r = client.get("/transactions")
    assert r.status_code == 401
    assert client.get("/app-lock/status").status_code == 401

    # Wrong credentials -> 401
    r = client.get("/transactions", auth=("alice", "wrong"))
    assert r.status_code == 401

    # Correct credentials reach a working endpoint on the isolated database.
    r = client.get("/transactions", auth=("alice", "secret"))
    assert r.status_code == 200
    assert client.get("/app-lock/status", auth=("alice", "secret")).status_code == 200


@pytest.mark.parametrize(
    ("username", "password"),
    [("alice", ""), ("", "secret")],
)
def test_partial_basic_auth_configuration_stops_startup(username, password, auth_settings):
    auth_settings(AUTH_USERNAME=username, AUTH_PASSWORD=password)
    with pytest.raises(ValidationError, match="must both be configured"):
        get_settings()


def test_api_documentation_is_disabled_by_default(auth_settings, monkeypatch):
    auth_settings(API_DOCS_ENABLED="false")
    # Only documentation routes need startup-time configuration; restore the app afterwards.
    monkeypatch.setattr(api_main, "app", api_main.app)
    configured_app = reload(api_main).app
    with TestClient(configured_app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
