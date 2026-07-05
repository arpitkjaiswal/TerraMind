"""
SQLAlchemy async engine + session factory.
All DB access goes through `get_db()` dependency.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

db_url = settings.DATABASE_URL
if settings.DEMO_MODE:
    db_url = "sqlite+aiosqlite:///./test.db"

is_sqlite = db_url.startswith("sqlite")

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    **(
        {} if is_sqlite else {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }
    )
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


from typing import AsyncGenerator

class Base(DeclarativeBase):
    __allow_unmapped__ = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
