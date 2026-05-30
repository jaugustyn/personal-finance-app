"""Smoke test: the FastAPI app starts and /health returns ok.

Note: importing apps.api.main triggers DB engine creation; we don't actually
hit the DB here because /health is independent.
"""
from fastapi.testclient import TestClient

from apps.api.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert "checks" in body
    assert "auth_enabled" in body
