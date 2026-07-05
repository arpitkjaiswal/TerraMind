"""
Celery tasks — async workers for the ingestion and memify pipelines.

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


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.ingest_status = "ready"
                doc.processed_at = datetime.now(timezone.utc)
                await db.commit()

        await set_ingest_status(document_id, "ready")
        log.info("task.cognify_done", document_id=document_id)

    try:
        _run_async(_inner())
    except Exception as exc:
        log.error("task.cognify_failed", document_id=document_id, error=str(exc), exc_info=True)
        _run_async(set_ingest_status(document_id, "ingest_failed", str(exc)))

        # Mark DB row failed on final retry
        if self.request.retries >= self.max_retries - 1:
            err_msg = str(exc)
            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.models.db import Document
                from sqlalchemy import select
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Document).where(Document.id == document_id))
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.ingest_status = "ingest_failed"
                        doc.ingest_error = f"Cognify failed after {self.max_retries} retries: {err_msg}"
                        await db.commit()
            _run_async(_mark_failed())
        raise


@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_memify_batch",
    max_retries=3,
    default_retry_delay=60,
)
def run_memify_batch(self, farm_id: str | None = None):
    """
    Nightly batch: re-processes all farms that have pending corrections
    so the knowledge graph improves over time.
    Also runs on-demand after any human correction via the corrections API.
    If farm_id is provided, only that farm is re-processed.
    """
    log.info("task.memify_batch_start", farm_id=farm_id)

    async def _inner():
        from app.core.database import AsyncSessionLocal
        from app.core.cognee_client import run_memify
        from app.core.redis_client import invalidate_query_cache
        from app.models.db import Correction, EvidenceEdge, QueryLog
        from sqlalchemy import select, distinct

        async with AsyncSessionLocal() as db:
            # Find all (farm_id, plot_id) pairs that have unprocessed corrections
            q = (
                select(
                    distinct(QueryLog.farm_id),
                    QueryLog.plot_id,
                )
                .join(EvidenceEdge, EvidenceEdge.query_id == QueryLog.id)
                .join(Correction, Correction.evidence_edge_id == EvidenceEdge.id)
                .where(Correction.memify_queued.is_(False))
            )
            if farm_id:
                q = q.where(QueryLog.farm_id == farm_id)
            result = await db.execute(q)
            pairs = result.all()

        for batch_farm_id, plot_id in pairs:
            try:
                await run_memify(farm_id=batch_farm_id, plot_id=plot_id)
                await invalidate_query_cache(batch_farm_id)

                # Mark corrections as queued
                async with AsyncSessionLocal() as db:
                    from sqlalchemy import update
                    await db.execute(
                        update(Correction)
                        .where(Correction.memify_queued.is_(False))
                        .values(memify_queued=True)
                    )
                    await db.commit()

                log.info("task.memify_done", farm_id=batch_farm_id, plot_id=plot_id)
            except Exception as exc:
                log.error("task.memify_farm_failed", farm_id=batch_farm_id, error=str(exc))

    try:
        _run_async(_inner())
    except Exception as exc:
        log.error("task.memify_batch_failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
