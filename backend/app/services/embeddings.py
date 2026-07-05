"""
Embedding service — generates vector embeddings for query text.
Used for semantic cache keying and Qdrant similarity search.

Falls back gracefully: if the embedding API is unavailable,
returns a zero vector so the query still completes (no cache hit).
"""

from __future__ import annotations
from typing import List
from functools import lru_cache

import structlog
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.circuit_breaker import llm_retry

log = structlog.get_logger(__name__)

EMBEDDING_DIM = 1536


@lru_cache(maxsize=1)
def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


@llm_retry
async def embed_text(text: str) -> List[float]:
    """
    Generate a 1536-dim embedding for a query string.
    Truncates to 8191 tokens (model limit).
    """
    if not settings.OPENAI_API_KEY:
        log.warning("embeddings.no_api_key_fallback")
        return [0.0] * EMBEDDING_DIM

    try:
        client = _get_openai_client()
        response = await client.embeddings.create(
            model=settings.COGNEE_EMBEDDING_MODEL,
            input=text[:20000],  # character limit approximation
        )
        return response.data[0].embedding
    except Exception as exc:
        log.error("embeddings.failed", error=str(exc))
        return [0.0] * EMBEDDING_DIM
