"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.dependencies.app_lock import require_app_unlock
from apps.api.middleware import (
    RateLimitMiddleware,
    RequestLogMiddleware,
    SecurityHeadersMiddleware,
)
from apps.api.routers import (
    accounts,
    anomalies,
    app_lock,
    assets,
    categories,
    chat,
    currencies,
    fixed_charges,
    forecast,
    imports,
    merchants,
    ml,
    profile,
    stats,
    subscriptions,
    transactions,
)
from apps.api.security import auth_enabled, require_auth
from finance.config import get_settings
from finance.db import SessionLocal, get_session
from finance.ml.classification.lifecycle import mark_interrupted_jobs
from finance.observability import configure_logging, get_logger

configure_logging()
logger = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().app_env != "test":
        try:
            with SessionLocal() as session:
                interrupted = mark_interrupted_jobs(session)
                if interrupted:
                    logger.warning("ml_training_jobs_interrupted", count=interrupted)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ml_training_job_recovery_failed", error=str(exc))
    logger.info(
        "api_started",
        auth_enabled=auth_enabled(),
    )
    yield


_settings = get_settings()
app = FastAPI(
    title="Personal Finance API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _settings.api_docs_enabled else None,
    redoc_url="/redoc" if _settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if _settings.api_docs_enabled else None,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_settings.trusted_hosts,
    www_redirect=False,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLogMiddleware)

_origins = _settings.cors_origins
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
if _settings.rate_limit_per_minute > 0:
    app.add_middleware(
        RateLimitMiddleware, max_per_minute=_settings.rate_limit_per_minute
    )


# Public endpoint (no auth) -------------------------------------------------
@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Minimal public liveness response without configuration disclosure."""
    return {"status": "ok"}


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
_app_lock_access = [Depends(require_auth)]
_protected = [Depends(require_auth), Depends(require_app_unlock)]
app.include_router(app_lock.router, dependencies=_app_lock_access)
app.include_router(accounts.router, dependencies=_protected)
app.include_router(imports.router, dependencies=_protected)
app.include_router(transactions.router, dependencies=_protected)
app.include_router(merchants.router, dependencies=_protected)
app.include_router(currencies.router, dependencies=_protected)
app.include_router(assets.router, dependencies=_protected)
app.include_router(fixed_charges.router, dependencies=_protected)
app.include_router(ml.router, dependencies=_protected)
app.include_router(forecast.router, dependencies=_protected)
app.include_router(anomalies.router, dependencies=_protected)
app.include_router(subscriptions.router, dependencies=_protected)
app.include_router(chat.router, dependencies=_protected)
app.include_router(stats.router, dependencies=_protected)
app.include_router(categories.router, dependencies=_protected)
app.include_router(profile.router, dependencies=_protected)
