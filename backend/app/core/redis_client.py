"""
Redis async client for:
  - Query result caching (TTL-based)
  - Distributed locking (prevent duplicate ingestion jobs)
  - Rate limit state (used by slowapi)
"""

from __future__ import annotations
from typing import Optional

import json
import uuid
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


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _query_cache_key(farm_id: str, query_hash: str) -> str:
    return f"aegis:query:{farm_id}:{query_hash}"


async def get_cached_query(farm_id: str, query_hash: str) -> Optional[dict]:
    try:
        redis = await get_redis_client()
        raw = await redis.get(_query_cache_key(farm_id, query_hash))
        if raw:
            log.info("redis.cache_hit", farm_id=farm_id, key=query_hash)
            return json.loads(raw)
    except Exception as exc:
        log.warning("redis.cache_read_failed", farm_id=farm_id, error=str(exc))
    return None


async def set_cached_query(
    farm_id: str,
    query_hash: str,
    result: dict,
    ttl: Optional[int] = None,
) -> None:
    try:
        redis = await get_redis_client()
        await redis.setex(
            _query_cache_key(farm_id, query_hash),
            ttl or settings.REDIS_CACHE_TTL_SECONDS,
            json.dumps(result, default=str),
        )
    except Exception as exc:
        log.warning("redis.cache_write_failed", farm_id=farm_id, error=str(exc))


async def invalidate_query_cache(farm_id: str) -> int:
    """Bust all cached queries for a farm (called after ingestion and corrections)."""
    try:
        redis = await get_redis_client()
        pattern = f"aegis:query:{farm_id}:*"
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                deleted += await redis.delete(*keys)
            if cursor == 0:
                return deleted
    except Exception as exc:
        log.warning("redis.cache_invalidation_failed", farm_id=farm_id, error=str(exc))
        return 0


# ── Distributed lock ──────────────────────────────────────────────────────────

class DistributedLock:
    """Simple Redis SET NX lock for preventing duplicate ingestion jobs."""

    def __init__(self, key: str, ttl: int = 300):
        self.key = f"aegis:lock:{key}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())

    async def __aenter__(self):
        redis = await get_redis_client()
        acquired = await redis.set(self.key, self.token, nx=True, ex=self.ttl)
        if not acquired:
            raise RuntimeError(f"Lock '{self.key}' already held — duplicate job prevented")
        return self

    async def __aexit__(self, *_):
        redis = await get_redis_client()
        await redis.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1,
            self.key,
            self.token,
        )


# ── Ingestion status tracking ──────────────────────────────────────────────────

async def set_ingest_status(document_id: str, status: str, detail: str = "") -> None:
    try:
        redis = await get_redis_client()
        await redis.setex(
            f"aegis:ingest:{document_id}",
            3600,
            json.dumps({"status": status, "detail": detail}),
        )
    except Exception as exc:
        log.warning("redis.ingest_status_write_failed", document_id=document_id, error=str(exc))


async def get_ingest_status(document_id: str) -> Optional[dict]:
    try:
        redis = await get_redis_client()
        raw = await redis.get(f"aegis:ingest:{document_id}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.warning("redis.ingest_status_read_failed", document_id=document_id, error=str(exc))
        return None
