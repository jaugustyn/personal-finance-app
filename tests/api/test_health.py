"""Smoke test: the FastAPI app starts and /health returns ok."""


def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
