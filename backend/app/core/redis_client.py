"""
Redis async client for:
  - Query result caching (TTL-based)
  - Distributed locking (prevent duplicate ingestion jobs)
  - Rate limit state (used by slowapi)
"""

from __future__ import annotations
from typing import Optional

import json
import redis.asyncio as aioredis
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _query_cache_key(farm_id: str, query_hash: str) -> str:
    return f"aegis:query:{farm_id}:{query_hash}"


async def get_cached_query(farm_id: str, query_hash: str) -> Optional[dict]:
    redis = await get_redis_client()
    raw = await redis.get(_query_cache_key(farm_id, query_hash))
    if raw:
        log.info("redis.cache_hit", farm_id=farm_id, key=query_hash)
        return json.loads(raw)
    return None


async def set_cached_query(
    farm_id: str,
    query_hash: str,
    result: dict,
    ttl: Optional[int] = None,
) -> None:
    redis = await get_redis_client()
    await redis.setex(
        _query_cache_key(farm_id, query_hash),
        ttl or settings.REDIS_CACHE_TTL_SECONDS,
        json.dumps(result, default=str),
    )


async def invalidate_query_cache(farm_id: str) -> int:
    """Bust all cached queries for a farm (called after corrections/memify)."""
    redis = await get_redis_client()
    pattern = f"aegis:query:{farm_id}:*"
    keys = await redis.keys(pattern)
    if keys:
        return await redis.delete(*keys)
    return 0


# ── Distributed lock ──────────────────────────────────────────────────────────

class DistributedLock:
    """Simple Redis SET NX lock for preventing duplicate ingestion jobs."""

    def __init__(self, key: str, ttl: int = 300):
        self.key = f"aegis:lock:{key}"
        self.ttl = ttl

    async def __aenter__(self):
        redis = await get_redis_client()
        acquired = await redis.set(self.key, "1", nx=True, ex=self.ttl)
        if not acquired:
            raise RuntimeError(f"Lock '{self.key}' already held — duplicate job prevented")
        return self

    async def __aexit__(self, *_):
        redis = await get_redis_client()
        await redis.delete(self.key)


# ── Ingestion status tracking ──────────────────────────────────────────────────

async def set_ingest_status(document_id: str, status: str, detail: str = "") -> None:
    redis = await get_redis_client()
    await redis.setex(
        f"aegis:ingest:{document_id}",
        3600,
        json.dumps({"status": status, "detail": detail}),
    )


async def get_ingest_status(document_id: str) -> Optional[dict]:
    redis = await get_redis_client()
    raw = await redis.get(f"aegis:ingest:{document_id}")
    return json.loads(raw) if raw else None
