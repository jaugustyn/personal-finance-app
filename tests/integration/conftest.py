"""Real database fixtures restricted to explicitly selected PostgreSQL test databases."""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from apps.api.main import app
from finance.categories import seed_system_categories
from finance.config import get_settings
from finance.db import get_session
from finance.domain.models import Base


def _test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "").strip()
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("PostgreSQL integration tests require a PostgreSQL database")
    if not (url.database or "").lower().endswith("_test"):
        pytest.fail("Refusing to clean a database whose name does not end with '_test'")
    return value


@pytest.fixture()
def postgres_reference(monkeypatch) -> Iterator[tuple[Session, TestClient]]:
    database_url = _test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"options": "-c timezone=UTC"},
        future=True,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))

    def override_session() -> Iterator[Session]:
        with session_factory() as request_session:
            yield request_session

    from apps.api.routers import imports as imports_router
    from finance.ingestion import service as ingestion_service
    from finance.llm import client as llm_client

    monkeypatch.setattr(imports_router, "_suggest_import_categories", lambda _id: None)
    monkeypatch.setattr(llm_client, "is_available", lambda: False)
    monkeypatch.setattr(
        ingestion_service,
        "prefetch_nbp_rates",
        lambda _session, **_kwargs: None,
    )
    app.dependency_overrides[get_session] = override_session
    session = session_factory()
    seed_system_categories(session)
    session.commit()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield session, client
    finally:
        session.close()
        app.dependency_overrides.pop(get_session, None)
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(delete(table))
        engine.dispose()
        get_settings.cache_clear()
