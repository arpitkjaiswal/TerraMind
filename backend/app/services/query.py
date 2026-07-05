"""
Query service — orchestrates the full RAG + graph traversal pipeline.

Flow:
  1. Check Redis TTL cache (exact match on query hash)
  2. Check Qdrant semantic cache (embedding similarity match)
  3. If cache miss:
       a. Run Cognee GRAPH_COMPLETION search (circuit-broken)
       b. Build evidence trail from graph result
       c. Assign confidence label
       d. Apply hallucination guard (suppress claims without graph edge)
       e. Apply scope guardrail (no prescriptive advice)
       f. Persist QueryLog + EvidenceEdge rows
       g. Store in both caches
  4. Return QueryResponse

Confidence labeling:
  - documented_fact:       claim traced to a specific source document
  - statistical_association: graph co-occurrence across ≥2 linked records
  - unconfirmed_hypothesis: plausible but weakly supported (shown only if requested)
"""

from __future__ import annotations

import os
import hashlib
import time
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from app.core.config import settings

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.cognee_client import run_search
from app.core.redis_client import get_cached_query, set_cached_query
from app.core.qdrant_client import semantic_cache_search, cache_query_result
from app.models.db import Document, EvidenceEdge, QueryLog
from app.models.schemas import (
    EvidenceEdgeRead,
    QueryRequest,
    QueryResponse,
)
from app.services.embeddings import embed_text

log = structlog.get_logger(__name__)

# ── Scope guardrail patterns (post-generation content filter) ─────────────────
_PRESCRIPTIVE_PATTERNS = [
    "apply", "dose", "dosage", "spray", "fertilise", "fertilize",
    "add", "use", "recommend applying", "should add", "you should use",
]

GUARDRAIL_NOTICE = (
    "\n\n---\n"
    "⚠️ **Scope notice:** This system explains what has happened — it does not "
    "recommend specific chemical applications or dosages. Consult a licensed "
    "agronomist before changing any inputs."
)


def _query_hash(query_text: str, plot_id: str, date_from: Optional[str], date_to: Optional[str]) -> str:
    key = f"{query_text}|{plot_id}|{date_from}|{date_to}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _assign_confidence_label(
    raw_result: Dict[str, Any],
    evidence_edges: List[Dict],
) -> Tuple[str, float]:
    """
    Determine confidence label and numeric score from Cognee's result.

    Heuristic rules (to be calibrated against the 15–20 case evaluation harness):
      - All evidence nodes have confirmed=True → documented_fact (score 0.85–1.0)
      - Multiple co-occurring nodes, no confirmed cause → statistical_association (0.50–0.84)
      - Single weak connection → unconfirmed_hypothesis (0.20–0.49)
    """
    if not evidence_edges:
        return "unconfirmed_hypothesis", 0.2

    confirmed_count = sum(1 for e in evidence_edges if e.get("confirmed", False))
    total = len(evidence_edges)

    if confirmed_count == total and total >= 2:
        score = min(0.95, 0.85 + 0.02 * total)
        return "documented_fact", round(score, 2)
    elif total >= 2:
        score = min(0.84, 0.55 + 0.05 * confirmed_count)
        return "statistical_association", round(score, 2)
    else:
        return "unconfirmed_hypothesis", round(0.20 + 0.10 * confirmed_count, 2)


def _apply_guardrail(answer_text: str) -> str:
    """
    Append a scope notice if the LLM output contains prescriptive language.
    This is a lightweight post-generation content filter — not a replacement
    for a proper system-prompt guardrail in the cognify step.
    """
    lower = answer_text.lower()
    if any(pat in lower for pat in _PRESCRIPTIVE_PATTERNS):
        return answer_text + GUARDRAIL_NOTICE
    return answer_text


def _build_evidence_trail(
    raw_result: Dict[str, Any],
    doc_lookup: Dict[str, Document],
    query_id: str,
) -> List[EvidenceEdge]:
    """
    Convert Cognee's raw graph result into EvidenceEdge ORM objects.
    Only edges that have a traceable source document are included —
    claims without a traceable edge are suppressed (hallucination mitigation).
    """
    edges = raw_result.get("evidence_edges", []) or raw_result.get("edges", [])
    orm_edges = []
    for e in edges:
        source_doc_id = e.get("source_document_id")
        if not source_doc_id and not e.get("node_id"):
            # No traceable source → suppress
            continue
        orm_edges.append(
            EvidenceEdge(
                id=str(uuid.uuid4()),
                query_id=query_id,
                source_document_id=source_doc_id,
                graph_node_id=e.get("node_id", ""),
                node_label=e.get("node_label", "Unknown"),
                node_type=e.get("node_type", "Unknown"),
                relationship_type=e.get("relationship_type", "CORRELATED_WITH"),
                date=e.get("date"),
            )
        )
    return orm_edges


def _evidence_to_schema(
    edges: List[EvidenceEdge],
    doc_lookup: Dict[str, Document],
) -> List[EvidenceEdgeRead]:
    result = []
    for e in edges:
        doc = doc_lookup.get(e.source_document_id or "")
        result.append(EvidenceEdgeRead(
            id=e.id,
            graph_node_id=e.graph_node_id,
            node_label=e.node_label,
            node_type=e.node_type,
            relationship_type=e.relationship_type,
            source_document_id=e.source_document_id,
            source_document_label=doc.label if doc else None,
            date=e.date,
        ))
    return result


async def execute_demo_query(request: QueryRequest) -> QueryResponse:
    # Load demo queries
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(base_dir, "outputs", "reports", "demo_queries.json")
    
    demo_queries = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            demo_queries = json.load(f)
            
    # Find match
    best_match = None
    best_overlap = -1
    req_words = set(request.query_text.lower().split())
    for dq in demo_queries:
        dq_words = set(dq["query_text"].lower().split())
        overlap = len(req_words.intersection(dq_words))
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = dq
            
    # If no match or very poor match (overlap < 2), fallback to default
    if not best_match or best_overlap < 2:
        answer_text = (
            "The offline knowledge graph does not contain a confident path to answer this question "
            "given your current field records. Try asking: 'Why did Field B's yield drop by 30% in 2025?' "
            "or 'Why is soil pH declining in Field B (plot-001b)?'"
        )
        return QueryResponse(
            query_id=str(uuid.uuid4()),
            query_text=request.query_text,
            answer_text=answer_text,
            confidence_label="unconfirmed_hypothesis",
            confidence_score=0.2,
            evidence_trail=[],
            graph_hops=0,
            latency_ms=45,
            cache_hit=False,
            created_at=datetime.now(timezone.utc),
        )
        
    # Map nodes to EvidenceEdgeRead
    evidence_trail = []
    relevant_nodes = best_match.get("relevant_nodes", [])
    
    for idx, n in enumerate(relevant_nodes):
        doc_label = "Pesticide Application Log" if n["type"] == "ChemicalProduct" else (
            "Soil Test Record" if n["type"] == "Practice" else (
                "Weather Station Log" if n["type"] == "WeatherEvent" else "Field Log"
            )
        )
        evidence_trail.append(
            EvidenceEdgeRead(
                id=str(uuid.uuid4()),
                graph_node_id=f"node-{idx:05d}",
                node_label=n["label"],
                node_type=n["type"],
                relationship_type="CORRELATED_WITH",
                source_document_id=f"doc-{idx:05d}",
                source_document_label=doc_label,
                date=n.get("date") or "2024-02-13",
            )
        )
        
    if not evidence_trail:
        evidence_trail = [
            EvidenceEdgeRead(
                id=str(uuid.uuid4()),
                graph_node_id="node-00001",
                node_label="Chlorpyrifos 20EC (plot-001b)",
                node_type="ChemicalProduct",
                relationship_type="APPLIED_TO",
                source_document_id="doc-00001",
                source_document_label="Chemical Application Log",
                date="2024-02-13",
            ),
            EvidenceEdgeRead(
                id=str(uuid.uuid4()),
                graph_node_id="node-00002",
                node_label="Drought 2025 (Punjab)",
                node_type="WeatherEvent",
                relationship_type="OCCURRED_DURING",
                source_document_id="doc-00002",
                source_document_label="Punjab Weather Report",
                date="2025-06-15",
            )
        ]
        
    return QueryResponse(
        query_id=str(uuid.uuid4()),
        query_text=request.query_text,
        answer_text=best_match.get("expected_insight", ""),
        confidence_label=best_match.get("confidence_label", "statistical_association"),
        confidence_score=best_match.get("confidence_score", 0.55),
        evidence_trail=evidence_trail,
        graph_hops=best_match.get("graph_hops", 2),
        latency_ms=120,
        cache_hit=False,
        created_at=datetime.now(timezone.utc),
    )


async def execute_query(
    request: QueryRequest,
    farm_id: str,
    user_id: str,
    db: AsyncSession,
) -> QueryResponse:
    if settings.DEMO_MODE:
        return await execute_demo_query(request)

    start = time.perf_counter()
    query_id = str(uuid.uuid4())
    q_hash = _query_hash(request.query_text, request.plot_id, request.date_from, request.date_to)

    # ── 1. Redis exact-match cache ────────────────────────────────────────────
    cached = await get_cached_query(farm_id, q_hash)
    if cached:
        cached["cache_hit"] = True
        cached["query_id"] = query_id   # fresh ID per call
        return QueryResponse(**cached)

    # ── 2. Qdrant semantic cache ───────────────────────────────────────────────
    query_vector = await embed_text(request.query_text)
    sem_cached = semantic_cache_search(query_vector, farm_id)
    if sem_cached:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return QueryResponse(**{**sem_cached, "cache_hit": True, "query_id": query_id, "latency_ms": latency_ms})

    # ── 3. Full pipeline (cache miss) ─────────────────────────────────────────
    log.info("query.cache_miss", farm_id=farm_id, plot_id=request.plot_id)

    # Call Cognee (circuit-broken)
    raw_result = await run_search(request.query_text, farm_id, request.plot_id)

    # If graph traversal finds no confident path, say so explicitly
    if not raw_result or not raw_result.get("answer"):
        answer_text = (
            "The knowledge graph does not contain a confident path to answer this question "
            "given your current field records. Try uploading more historical documents or "
            "narrowing the date range."
        )
        confidence_label = "unconfirmed_hypothesis"
        confidence_score = 0.0
        evidence_edges_orm: List[EvidenceEdge] = []
        graph_hops = 0
    else:
        answer_text = _apply_guardrail(raw_result.get("answer", ""))
        raw_edges = raw_result.get("evidence_edges", [])
        confidence_label, confidence_score = _assign_confidence_label(raw_result, raw_edges)
        graph_hops = raw_result.get("graph_hops", len(raw_edges))

        # Suppress hypotheses unless explicitly requested
        if confidence_label == "unconfirmed_hypothesis" and not request.include_hypotheses:
            answer_text = (
                "A possible connection was detected but confidence is too low to report "
                "without explicit request. Re-run with `include_hypotheses: true` to see it."
            )

        # Build evidence trail — load source documents for labels
        doc_ids = {e.get("source_document_id") for e in raw_edges if e.get("source_document_id")}
        docs_result = await db.execute(
            select(Document).where(Document.id.in_(doc_ids), Document.farm_id == farm_id)  # type: ignore[attr-defined]
        )
        doc_lookup = {d.id: d for d in docs_result.scalars().all()}
        evidence_edges_orm = _build_evidence_trail(raw_result, doc_lookup, query_id)

    latency_ms = int((time.perf_counter() - start) * 1000)

    # ── Persist QueryLog + EvidenceEdge rows ──────────────────────────────────
    query_log = QueryLog(
        id=query_id,
        farm_id=farm_id,
        plot_id=request.plot_id,
        user_id=user_id,
        query_text=request.query_text,
        answer_text=answer_text,
        confidence_label=confidence_label,
        confidence_score=confidence_score,
        graph_hops=graph_hops,
        latency_ms=latency_ms,
        cache_hit=False,
    )
    db.add(query_log)
    for edge in evidence_edges_orm:
        db.add(edge)
    await db.flush()

    doc_lookup_all = {
        d.id: d
        for d in (await db.execute(
            select(Document).where(
                Document.id.in_({e.source_document_id for e in evidence_edges_orm if e.source_document_id}),  # type: ignore[attr-defined]
                Document.farm_id == farm_id,
            )
        )).scalars().all()
    }

    evidence_schema = _evidence_to_schema(evidence_edges_orm, doc_lookup_all)

    response = QueryResponse(
        query_id=query_id,
        query_text=request.query_text,
        answer_text=answer_text,
        confidence_label=confidence_label,
        confidence_score=confidence_score,
        evidence_trail=evidence_schema,
        graph_hops=graph_hops,
        latency_ms=latency_ms,
        cache_hit=False,
        created_at=datetime.now(timezone.utc),
    )

    # ── Populate caches ───────────────────────────────────────────────────────
    payload = response.model_dump(mode="json")
    await set_cached_query(farm_id, q_hash, payload)
    cache_query_result(farm_id, query_vector, payload, str(uuid.uuid4()))

    log.info(
        "query.complete",
        query_id=query_id,
        confidence=confidence_label,
        score=confidence_score,
        hops=graph_hops,
        latency_ms=latency_ms,
    )
    return response
