"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.middleware import (
    RateLimitMiddleware,
    RequestLogMiddleware,
    SecurityHeadersMiddleware,
)
from apps.api.routers import (
    anomalies,
    assets,
    categories,
    chat,
    forecast,
    imports,
    ml,
    profile,
    stats,
    subscriptions,
    transactions,
)
from apps.api.scheduler import shutdown as scheduler_shutdown
from apps.api.scheduler import start as scheduler_start
from apps.api.security import auth_enabled, require_auth
from finance.config import get_settings
from finance.db import engine, get_session
from finance.llm.client import is_available as ollama_is_available
from finance.observability import configure_logging, get_logger

configure_logging()
logger = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler_start()
    logger.info(
        "api_started",
        auth_enabled=auth_enabled(),
        scheduler_enabled=get_settings().scheduler_enabled,
    )
    yield
    scheduler_shutdown()


app = FastAPI(title="Personal Finance API", version="0.1.0", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLogMiddleware)

_settings = get_settings()
_origins = [o.strip() for o in _settings.cors_allow_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
if _settings.rate_limit_per_minute > 0:
    app.add_middleware(
        RateLimitMiddleware, max_per_minute=_settings.rate_limit_per_minute
    )


# Public endpoint (no auth) -------------------------------------------------
@app.get("/health")
def health() -> dict[str, object]:
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_db_failed", error=str(exc))
    return {
        "status": "ok" if db_ok else "degraded",
        "time": datetime.now(UTC).isoformat(),
        "checks": {
            "database": db_ok,
            "ollama": ollama_is_available(),
        },
        "auth_enabled": auth_enabled(),
    }


@app.get("/health/live", include_in_schema=False)
def health_live() -> dict[str, str]:
    """Liveness probe: process is up and event loop responsive."""
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def health_ready(session: Session = Depends(get_session)):
    """Readiness probe: required dependencies (DB) reachable."""
    from fastapi.responses import JSONResponse

    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_ready_db_failed", error=str(exc))
        return JSONResponse(
            {"status": "not_ready", "checks": {"database": False}},
            status_code=503,
        )
    return {"status": "ready", "checks": {"database": True}}


# Protected routers (BasicAuth applied conditionally on each request) ------
_protected = [Depends(require_auth)]
app.include_router(imports.router, dependencies=_protected)
app.include_router(transactions.router, dependencies=_protected)
app.include_router(ml.router, dependencies=_protected)
app.include_router(forecast.router, dependencies=_protected)
app.include_router(anomalies.router, dependencies=_protected)
app.include_router(subscriptions.router, dependencies=_protected)
app.include_router(chat.router, dependencies=_protected)
app.include_router(stats.router, dependencies=_protected)
app.include_router(assets.router, dependencies=_protected)
app.include_router(categories.router, dependencies=_protected)
app.include_router(profile.router, dependencies=_protected)
