"""
Qdrant vector store client.

Provides a singleton QdrantClient and helper functions for:
  - Collection provisioning (per-farm, idempotent)
  - Upsert vectors with agronomic payload
  - Semantic similarity search (used for semantic cache keying)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from functools import lru_cache

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.core.config import settings

log = structlog.get_logger(__name__)

EMBEDDING_DIM = 1536  # text-embedding-3-small output dimension


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    kwargs: Dict[str, Any] = {"host": settings.QDRANT_HOST, "port": settings.QDRANT_PORT}
    if settings.QDRANT_API_KEY:
        kwargs["api_key"] = settings.QDRANT_API_KEY
    return QdrantClient(**kwargs)


def collection_name(farm_id: str) -> str:
    return f"{settings.QDRANT_COLLECTION_PREFIX}{farm_id}"


def ensure_collection(farm_id: str) -> None:
    """Create the Qdrant collection for a farm if it doesn't already exist."""
    client = get_qdrant_client()
    name = collection_name(farm_id)
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        log.info("qdrant.collection_created", collection=name)


def upsert_vectors(
    farm_id: str,
    points: List[PointStruct],
) -> None:
    client = get_qdrant_client()
    client.upsert(collection_name=collection_name(farm_id), points=points)


def search_similar(
    farm_id: str,
    query_vector: List[float],
    limit: int = 10,
    plot_id: Optional[str] = None,
    score_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Semantic similarity search within a farm's collection.
    Optionally filtered to a specific plot.
    """
    client = get_qdrant_client()
    filters = None
    if plot_id:
        filters = Filter(must=[FieldCondition(key="plot_id", match=MatchValue(value=plot_id))])

    results = client.search(
        collection_name=collection_name(farm_id),
        query_vector=query_vector,
        limit=limit,
        query_filter=filters,
        score_threshold=score_threshold,
        with_payload=True,
    )
    return [
        {"id": str(r.id), "score": r.score, "payload": r.payload}
        for r in results
    ]


def semantic_cache_search(
    query_vector: List[float],
    farm_id: str,
    threshold: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Look for a semantically similar cached query result.
    Returns the cached payload if found above threshold, else None.
    """
    threshold = threshold or settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD
    client = get_qdrant_client()
    cache_collection = f"{settings.QDRANT_COLLECTION_PREFIX}query_cache"

    # Ensure cache collection exists
    existing = {c.name for c in client.get_collections().collections}
    if cache_collection not in existing:
        client.create_collection(
            collection_name=cache_collection,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )

    farm_filter = Filter(must=[FieldCondition(key="farm_id", match=MatchValue(value=farm_id))])
    results = client.search(
        collection_name=cache_collection,
        query_vector=query_vector,
        limit=1,
        query_filter=farm_filter,
        score_threshold=threshold,
        with_payload=True,
    )
    if results:
        log.info("qdrant.semantic_cache_hit", score=results[0].score)
        return results[0].payload
    return None


def cache_query_result(
    farm_id: str,
    query_vector: List[float],
    result_payload: Dict[str, Any],
    point_id: str,
) -> None:
    """Store a query result in the semantic cache collection."""
    client = get_qdrant_client()
    cache_collection = f"{settings.QDRANT_COLLECTION_PREFIX}query_cache"
    client.upsert(
        collection_name=cache_collection,
        points=[PointStruct(id=point_id, vector=query_vector, payload={"farm_id": farm_id, **result_payload})],
    )
