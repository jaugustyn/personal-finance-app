"""Database session and engine factory."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from finance.config import get_settings

_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI-friendly dependency yielding a session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
