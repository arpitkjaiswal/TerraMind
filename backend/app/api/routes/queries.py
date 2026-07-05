"""
Query route — the primary diagnostic endpoint.

POST /api/v1/query/          → run a diagnostic query
GET  /api/v1/query/history   → list past queries for a plot
GET  /api/v1/query/{id}      → retrieve a specific past query with evidence

Rate-limited: 20/minute per API key (stricter than default).
"""

from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import get_current_token_data, TokenData
from app.core.config import settings
from app.core.database import get_db
from app.models.db import EvidenceEdge, QueryLog
from app.models.schemas import (
    EvidenceEdgeRead,
    QueryListItem,
    QueryRequest,
    QueryResponse,
)
from app.services.query import execute_query

log = structlog.get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=QueryResponse)
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def run_query(
    request: Request,
    body: QueryRequest,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    """
    Primary diagnostic endpoint.

    Request body:
      - query_text: plain-language question (5–2000 chars)
      - plot_id: which field to query
      - date_from / date_to: optional temporal filter
      - include_hypotheses: show weakly-supported connections (default false)

    Response:
      {
        answer_text,
        confidence_label,      ← "documented_fact" | "statistical_association" | "unconfirmed_hypothesis"
        confidence_score,      ← 0.0–1.0
        evidence_trail[],      ← [{node_label, source_document, date, relationship_type}, ...]
        graph_hops,
        latency_ms,
        cache_hit
      }
    """
    return await execute_query(
        request=body,
        farm_id=td.farm_id,
        user_id=td.user_id,
        db=db,
    )


@router.get("/history", response_model=list[QueryListItem])
async def query_history(
    plot_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    q = select(QueryLog).where(QueryLog.farm_id == td.farm_id)
    if plot_id:
        q = q.where(QueryLog.plot_id == plot_id)
    q = q.order_by(QueryLog.created_at.desc()).limit(limit).offset(offset)  # type: ignore[attr-defined]
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        QueryListItem(
            query_id=r.id,
            query_text=r.query_text,
            confidence_label=r.confidence_label or "unconfirmed_hypothesis",
            confidence_score=r.confidence_score or 0.0,
            latency_ms=r.latency_ms or 0,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: str,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QueryLog).where(QueryLog.id == query_id, QueryLog.farm_id == td.farm_id)
    )
    ql = result.scalar_one_or_none()
    if not ql:
        raise HTTPException(status_code=404, detail="Query not found")

    # Load evidence edges + source document labels
    edges_result = await db.execute(
        select(EvidenceEdge).where(EvidenceEdge.query_id == query_id)
    )
    edges = edges_result.scalars().all()

    from app.models.db import Document
    doc_ids = {e.source_document_id for e in edges if e.source_document_id}
    docs_result = await db.execute(
        select(Document).where(Document.id.in_(doc_ids), Document.farm_id == td.farm_id)  # type: ignore[attr-defined]
    )
    doc_lookup = {d.id: d for d in docs_result.scalars().all()}

    evidence_schema = [
        EvidenceEdgeRead(
            id=e.id,
            graph_node_id=e.graph_node_id,
            node_label=e.node_label,
            node_type=e.node_type,
            relationship_type=e.relationship_type,
            source_document_id=e.source_document_id,
            source_document_label=doc_lookup.get(e.source_document_id, None) and
                doc_lookup[e.source_document_id].label,
            date=e.date,
        )
        for e in edges
    ]

    return QueryResponse(
        query_id=ql.id,
        query_text=ql.query_text,
        answer_text=ql.answer_text or "",
        confidence_label=ql.confidence_label or "unconfirmed_hypothesis",
        confidence_score=ql.confidence_score or 0.0,
        evidence_trail=evidence_schema,
        graph_hops=ql.graph_hops or 0,
        latency_ms=ql.latency_ms or 0,
        cache_hit=ql.cache_hit,
        created_at=ql.created_at,
    )
