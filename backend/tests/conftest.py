"""
Pytest configuration — shared fixtures for all tests.

Provides:
  - Async test client (httpx + ASGI)
  - In-memory SQLite for DB tests
  - Mocked Neo4j, Qdrant, Redis, Cognee, S3
  - JWT tokens for farmer/agronomist/admin roles
"""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
settings.DEMO_MODE = False

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import create_access_token
from app.core.database import Base, get_db
from app.main import app
from app.models.db import Farm, Plot, User
from app.core.auth import hash_password

# ── Test database (SQLite in-memory) ─────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Seed data ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_farm(db: AsyncSession) -> Farm:
    import uuid
    farm = Farm(id=str(uuid.uuid4()), name="Test Farm", owner_user_id="placeholder")
    db.add(farm)
    await db.flush()
    return farm


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, test_farm: Farm) -> User:
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        farm_id=test_farm.id,
        email="farmer@test.com",
        hashed_password=hash_password("test1234"),
        role="farmer",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_agronomist(db: AsyncSession, test_farm: Farm) -> User:
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        farm_id=test_farm.id,
        email="agro@test.com",
        hashed_password=hash_password("test1234"),
        role="agronomist",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_plot(db: AsyncSession, test_farm: Farm) -> Plot:
    import uuid
    plot = Plot(
        id=str(uuid.uuid4()),
        farm_id=test_farm.id,
        name="Field B — South Valley",
        crop_type="Corn",
        size_ha=38.2,
    )
    db.add(plot)
    await db.flush()
    return plot


# ── JWT tokens ────────────────────────────────────────────────────────────────

@pytest.fixture
def farmer_token(test_user: User, test_farm: Farm) -> str:
    return create_access_token(test_user.id, test_farm.id, "farmer")


@pytest.fixture
def agronomist_token(test_agronomist: User, test_farm: Farm) -> str:
    return create_access_token(test_agronomist.id, test_farm.id, "agronomist")


# ── ASGI test client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with overridden DB dependency."""
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Mock external services ────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_neo4j():
    with patch("app.core.neo4j_client.neo4j_driver") as m:
        m.session.return_value.__aenter__ = AsyncMock()
        m.session.return_value.__aexit__ = AsyncMock(return_value=False)
        yield m


@pytest.fixture(autouse=True)
def mock_redis():
    with patch("app.core.redis_client._redis_client") as m:
        m.ping = AsyncMock(return_value=True)
        m.get = AsyncMock(return_value=None)
        m.setex = AsyncMock()
        m.delete = AsyncMock(return_value=0)
        m.keys = AsyncMock(return_value=[])
        yield m


@pytest.fixture(autouse=True)
def mock_qdrant():
    with patch("app.core.qdrant_client.get_qdrant_client") as m:
        client = MagicMock()
        client.get_collections.return_value = MagicMock(collections=[])
        client.search.return_value = []
        m.return_value = client
        yield client


@pytest.fixture(autouse=True)
def mock_cognee():
    with patch("app.core.cognee_client.cognee") as m:
        m.config = MagicMock()
        m.add = AsyncMock()
        m.cognify = AsyncMock()
        m.search = AsyncMock(return_value={
            "answer": "Test answer from mocked Cognee.",
            "evidence_edges": [
                {"node_id": "n-001", "node_label": "Chlorpyrifos-X", "node_type": "ChemicalProduct",
                 "relationship_type": "APPLIED_TO", "source_document_id": None, "date": "2024-04-10", "confirmed": True}
            ],
            "graph_hops": 2,
        })
        m.memify = AsyncMock()
        yield m


@pytest.fixture(autouse=True)
def mock_s3():
    with patch("app.services.storage._session") as m:
        s3_client = AsyncMock()
        s3_client.put_object = AsyncMock()
        s3_client.get_object_tagging = AsyncMock(side_effect=Exception("NoSuchKey"))
        s3_client.generate_presigned_url = AsyncMock(return_value="https://s3.example.com/presigned")
        m.client.return_value.__aenter__ = AsyncMock(return_value=s3_client)
        m.client.return_value.__aexit__ = AsyncMock(return_value=False)
        yield s3_client
