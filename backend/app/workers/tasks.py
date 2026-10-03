"""
Celery tasks — async workers for ingestion and correction enrichment.

These run in a separate process pool from the FastAPI app.
Each task has structured logging, retry with exponential backoff,
and writes the final status back to Postgres and Redis.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app
from app.core.redis_client import set_ingest_status

log = structlog.get_logger(__name__)
_worker_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    """Use one event loop per Celery process so async connection pools stay valid."""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop.run_until_complete(coro)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.cognify_document",
    max_retries=5,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def cognify_document(self, document_id: str, farm_id: str, plot_id: str, text: str):
    """
    Async Cognee extract → cognify pipeline for a single document.
    Marks the Document row ready on success, ingest_failed on final failure.
    """
    log.info("task.cognify_start", document_id=document_id, task_id=self.request.id)

    async def _inner():
        from app.core.cognee_client import run_extract, run_cognify
        from app.core.database import AsyncSessionLocal
        from app.models.db import Document
        from sqlalchemy import select

        dataset_name = f"farm_{farm_id}_plot_{plot_id}"

        # Extract
        await run_extract(text, dataset_name)

        # Cognify (constrained to agronomic ontology)
        await run_cognify(
            dataset_name=dataset_name,
            farm_id=farm_id,
            plot_id=plot_id,
            source_document_id=document_id,
        )

        # Mark ready in DB
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Document).where(
                Document.id == document_id,
                Document.farm_id == farm_id,
                Document.plot_id == plot_id,
            ))
            doc = result.scalar_one_or_none()
            if doc:
                doc.ingest_status = "ready"
                doc.processed_at = datetime.now(timezone.utc)
                await db.commit()

        await set_ingest_status(document_id, "ready")
        from app.core.redis_client import invalidate_query_cache
        await invalidate_query_cache(farm_id)
        log.info("task.cognify_done", document_id=document_id)

    try:
        _run_async(_inner())
    except Exception as exc:
        log.error("task.cognify_failed", document_id=document_id, error=str(exc), exc_info=True)
        if self.request.retries >= self.max_retries:
            err_msg = str(exc)
            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.models.db import Document
                from sqlalchemy import select
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Document).where(
                        Document.id == document_id,
                        Document.farm_id == farm_id,
                        Document.plot_id == plot_id,
                    ))
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.ingest_status = "ingest_failed"
                        doc.ingest_error = f"Processing failed after retries: {err_msg[:1000]}"
                        await db.commit()
            _run_async(_mark_failed())
            _run_async(set_ingest_status(document_id, "ingest_failed", "Processing failed after retries."))
        else:
            _run_async(set_ingest_status(document_id, "processing", "Processing will retry."))
        raise


@celery_app.task(
    bind=True,
    name="app.workers.tasks.memify_correction",
    max_retries=5,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def memify_correction(self, correction_id: str, farm_id: str, plot_id: str):
    """Apply one farm and plot scoped correction through Cognee's memify API."""
    async def _inner():
        from sqlalchemy import select
        from app.core.cognee_client import run_memify
        from app.core.database import AsyncSessionLocal
        from app.models.db import Correction, EvidenceEdge, QueryLog

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Correction, EvidenceEdge)
                .join(EvidenceEdge, EvidenceEdge.id == Correction.evidence_edge_id)
                .join(QueryLog, QueryLog.id == EvidenceEdge.query_id)
                .where(
                    Correction.id == correction_id,
                    QueryLog.farm_id == farm_id,
                    QueryLog.plot_id == plot_id,
                )
            )
            row = result.one_or_none()
            if row is None:
                raise ValueError("Correction not found in the requested farm and plot")
            correction, edge = row
            note = correction.correction_note
            node_id = edge.graph_node_id

        await run_memify(farm_id, plot_id, note, node_id)
        from app.core.redis_client import invalidate_query_cache
        await invalidate_query_cache(farm_id)

    log.info("task.memify_correction_start", correction_id=correction_id, task_id=self.request.id)
    _run_async(_inner())
    log.info("task.memify_correction_done", correction_id=correction_id)
