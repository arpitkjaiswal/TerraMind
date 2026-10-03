"""Health and readiness probes — never expose connection details in responses."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core import neo4j_client, qdrant_client
from app.core.redis_client import get_redis_client
from app.core.config import settings
from app.models.schemas import HealthCheck

router = APIRouter()


async def _service_status(db: AsyncSession) -> dict[str, str]:
    services: dict[str, str] = {}

    # Postgres
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception:
        services["postgres"] = "unavailable"

    if settings.DEMO_MODE:
        return services

    # Neo4j
    try:
        async with neo4j_client.neo4j_driver.session() as session:
            await session.run("RETURN 1")
        services["neo4j"] = "ok"
    except Exception:
        services["neo4j"] = "unavailable"

    # Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "unavailable"

    try:
        await asyncio.to_thread(qdrant_client.get_qdrant_client().get_collections)
        services["qdrant"] = "ok"
    except Exception:
        services["qdrant"] = "unavailable"

    return services


@router.get("/health", response_model=HealthCheck, tags=["Health"])
async def health(response: Response, db: AsyncSession = Depends(get_db)):
    services = await _service_status(db)

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    if overall != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthCheck(status=overall, version=settings.APP_VERSION, services=services)


@router.get("/ready", tags=["Health"])
async def readiness(db: AsyncSession = Depends(get_db)):
    """Return 503 until the required data services can accept real traffic."""
    services = await _service_status(db)
    ready = all(value == "ok" for value in services.values())
    if not ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"ready": False, "services": services})
    return {"ready": True, "services": services}
