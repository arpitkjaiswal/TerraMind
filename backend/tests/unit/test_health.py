import pytest
from fastapi import HTTPException, Response
from unittest.mock import AsyncMock

from app.core import config
from app.api.routes import health


@pytest.mark.asyncio
async def test_service_status_checks_all_dependencies(monkeypatch, mock_redis, mock_qdrant):
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    db = AsyncMock()

    services = await health._service_status(db)

    assert services == {
        "postgres": "ok",
        "neo4j": "ok",
        "redis": "ok",
        "qdrant": "ok",
    }
    db.execute.assert_awaited_once()
    mock_redis.ping.assert_awaited_once()
    mock_qdrant.get_collections.assert_called_once()


@pytest.mark.asyncio
async def test_service_status_reports_database_failure_in_demo_mode(monkeypatch):
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("database detail must stay private")

    services = await health._service_status(db)

    assert services == {"postgres": "unavailable"}


@pytest.mark.asyncio
async def test_health_sets_service_unavailable_status(monkeypatch):
    monkeypatch.setattr(
        health,
        "_service_status",
        AsyncMock(return_value={"postgres": "unavailable"}),
    )
    response = Response()

    result = await health.health(response, AsyncMock())

    assert response.status_code == 503
    assert result.status == "degraded"


@pytest.mark.asyncio
async def test_readiness_fails_with_degraded_services(monkeypatch):
    monkeypatch.setattr(
        health,
        "_service_status",
        AsyncMock(return_value={"postgres": "ok", "redis": "unavailable"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await health.readiness(AsyncMock())

    assert getattr(exc_info.value, "status_code", None) == 503

