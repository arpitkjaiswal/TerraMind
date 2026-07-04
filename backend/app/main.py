"""
Aegis Backend — FastAPI application entry point.

Wires together:
  - CORS, security headers
  - Auth router (login / refresh)
  - API v1 routers (farms, plots, documents, queries, corrections)
  - Prometheus metrics
  - OpenTelemetry tracing
  - Structured logging (structlog)
  - Startup / shutdown lifecycle (DB pool, Neo4j driver, Qdrant, Redis, Cognee)
  - Global exception handlers
  - Rate limiting (slowapi)
"""

import time
import uuid

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import engine, Base
from app.core.neo4j_client import neo4j_driver
from app.core.qdrant_client import get_qdrant_client
from app.core.redis_client import get_redis_client
from app.core.cognee_client import init_cognee

from app.api.routes import auth, farms, plots, documents, queries, corrections, health

# ── Logging ───────────────────────────────────────────────────────────────────
configure_logging()
log = structlog.get_logger(__name__)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("aegis.startup", version=settings.APP_VERSION, env=settings.APP_ENV)

    # Create Postgres tables (in production, use Alembic migrations instead)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("aegis.db.tables_ready")

    # Verify Neo4j connectivity
    async with neo4j_driver.session() as session:
        await session.run("RETURN 1")
    log.info("aegis.neo4j.connected", uri=settings.NEO4J_URI)

    # Verify Qdrant
    qdrant = get_qdrant_client()
    qdrant.get_collections()
    log.info("aegis.qdrant.connected")

    # Verify Redis
    redis = await get_redis_client()
    await redis.ping()
    log.info("aegis.redis.connected")

    # Initialise Cognee with our provider config
    await init_cognee()
    log.info("aegis.cognee.initialized")

    yield  # ── app is running ──

    # Teardown
    await engine.dispose()
    await neo4j_driver.close()
    log.info("aegis.shutdown")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Aegis — Longitudinal Agronomy API",
    description=(
        "Temporal knowledge-graph digital twin for farmland. "
        "Ingests field notes, weather data, and chemical logs; "
        "answers diagnostic queries with a transparent evidence trail."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts (defence against host-header injection in prod)
if not settings.DEBUG:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)


@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    """Attach a correlation ID to every request and emit structured access log."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    log.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    structlog.contextvars.unbind_contextvars("request_id")

    response.headers["X-Request-ID"] = request_id
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Prometheus metrics ─────────────────────────────────────────────────────────
if settings.PROMETHEUS_METRICS_ENABLED:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router,        prefix="/auth",           tags=["Auth"])
app.include_router(farms.router,       prefix="/api/v1/farms",   tags=["Farms"])
app.include_router(plots.router,       prefix="/api/v1/plots",   tags=["Plots"])
app.include_router(documents.router,   prefix="/api/v1/documents", tags=["Documents"])
app.include_router(queries.router,     prefix="/api/v1/query",   tags=["Query"])
app.include_router(corrections.router, prefix="/api/v1/corrections", tags=["Corrections"])


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", exc=str(exc), path=request.url.path, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": getattr(request.state, "request_id", None)},
    )
