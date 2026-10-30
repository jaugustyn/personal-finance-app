"""The cleanup fixture must reject unsafe database targets before connecting."""
import pytest

from tests.integration.conftest import _test_database_url


@pytest.mark.parametrize("url, message", [
    ("postgresql+psycopg://localhost/finance", "does not end"),
    ("postgresql+psycopg://localhost", "does not end"),
    ("sqlite:///finance_test", "require a PostgreSQL"),
])
def test_postgres_fixture_rejects_unsafe_target(monkeypatch, url, message) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    with pytest.raises(pytest.fail.Exception, match=message):
        _test_database_url()


def test_postgres_fixture_requires_explicit_url(monkeypatch) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(pytest.skip.Exception, match="TEST_DATABASE_URL is required"):
        _test_database_url()
