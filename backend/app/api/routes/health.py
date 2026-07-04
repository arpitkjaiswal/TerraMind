"""Health check routes — used by load balancers and readiness probes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.neo4j_client import neo4j_driver
from app.core.redis_client import get_redis_client
from app.core.config import settings
from app.models.schemas import HealthCheck

router = APIRouter()


@router.get("/health", response_model=HealthCheck, tags=["Health"])
async def health(db: AsyncSession = Depends(get_db)):
    services = {}

    # Postgres
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception as e:
        services["postgres"] = f"error: {e}"

    # Neo4j
    try:
        async with neo4j_driver.session() as session:
            await session.run("RETURN 1")
        services["neo4j"] = "ok"
    except Exception as e:
        services["neo4j"] = f"error: {e}"

    # Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        services["redis"] = "ok"
    except Exception as e:
        services["redis"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return HealthCheck(status=overall, version=settings.APP_VERSION, services=services)


@router.get("/ready", tags=["Health"])
async def readiness():
    """Kubernetes readiness probe — always 200 if app is up."""
    return {"ready": True}
