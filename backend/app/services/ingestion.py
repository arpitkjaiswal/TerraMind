"""
Document ingestion pipeline (saga pattern).

Each step writes back to the Document row so a failed step leaves the
document in a consistent, inspectable state rather than an undefined one.

Saga steps:
  1. Upload raw file to S3                         → storage_uri, content_hash
  2. Extract text (OCR or PDF parse)               → extracted_text, source_confidence
  3. Route by confidence:
       ≥ threshold → queue Cognee cognify job       → ingest_status = "processing"
       in range    → flag for human review          → ingest_status = "pending_review"
       < reject    → mark ingest_failed             → ingest_status = "ingest_failed"
  4. Cognify (Celery async task)                   → graph + vector nodes created
  5. Mark ready                                    → ingest_status = "ready"

On any unhandled exception: mark ingest_failed + log error (never silent).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.redis_client import set_ingest_status
from app.core.redis_client import invalidate_query_cache
from app.models.db import Document
from app.services.ocr import extract_text, extract_text_from_pdf, OCRResult
from app.services.storage import upload_document, compute_content_hash
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


async def ingest_document(
    db: AsyncSession,
    farm_id: str,
    plot_id: str,
    filename: str,
    content: bytes,
    source_type: str,  # "pdf" | "photo" | "csv"
    label: str,
    date_of_event: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Document:
    """
    Entry point for document ingestion. Creates the DB row, runs the OCR
    saga, and dispatches async Cognify task if confidence is sufficient.
    """
    document_id = str(uuid.uuid4())
    content_hash = compute_content_hash(content)

    # ── Idempotency: reject exact duplicate content within the same plot ──────
    existing = await db.execute(
        select(Document).where(
            Document.plot_id == plot_id,
            Document.content_hash == content_hash,
        )
    )
    if dup := existing.scalar_one_or_none():
        log.info("ingestion.duplicate_skipped", document_id=dup.id, content_hash=content_hash)
        return dup

    # ── Create DB row immediately (saga start) ────────────────────────────────
    doc = Document(
        id=document_id,
        farm_id=farm_id,
        plot_id=plot_id,
        source_type=source_type,
        label=label,
        storage_uri="",             # filled after S3 upload
        content_hash=content_hash,
        ingest_status="pending_ocr",
        date_of_event=date_of_event,
        doc_metadata=metadata or {},
    )
    db.add(doc)
    try:
        await db.flush()
    except IntegrityError:
        # The unique (plot_id, content_hash) index arbitrates concurrent uploads.
        await db.rollback()
        existing = await db.scalar(select(Document).where(
            Document.plot_id == plot_id,
            Document.content_hash == content_hash,
        ))
        if existing is not None:
            return existing
        raise

    await set_ingest_status(document_id, "pending_ocr")

    try:
        # ── Step 1: Upload to S3 ──────────────────────────────────────────────
        storage_uri, _ = await upload_document(
            farm_id, plot_id, document_id, filename, content
        )
        doc.storage_uri = storage_uri

        # ── Step 2: Extract text ──────────────────────────────────────────────
        if source_type == "pdf":
            ocr_result = await extract_text_from_pdf(content)
        elif source_type == "photo":
            content_type = _guess_image_type(filename)
            ocr_result = await extract_text(content, content_type)
        else:
            # CSV / structured data — no OCR needed, treat as fully confident
            ocr_result = _passthrough_csv(content, filename)

        doc.extracted_text = ocr_result.text
        doc.source_confidence = ocr_result.confidence

        # ── Step 3: Route by confidence ───────────────────────────────────────
        if ocr_result.should_reject:
            doc.ingest_status = "ingest_failed"
            doc.ingest_error = f"OCR confidence {ocr_result.confidence:.2%} below rejection threshold"
            await set_ingest_status(document_id, "ingest_failed", doc.ingest_error)
            log.warning("ingestion.rejected_low_confidence", document_id=document_id, confidence=ocr_result.confidence)

        elif ocr_result.needs_review:
            doc.ingest_status = "pending_review"
            await set_ingest_status(document_id, "pending_review")
            log.info("ingestion.queued_for_review", document_id=document_id, confidence=ocr_result.confidence)

        else:
            # High confidence → dispatch async Cognify job
            doc.ingest_status = "processing"
            await set_ingest_status(document_id, "processing")

        doc.processed_at = datetime.now(timezone.utc)
        await db.flush()
        # Commit the row before publishing a worker task; otherwise a fast worker
        # can run before the API dependency commits and fail to find the document.
        await db.commit()
        if doc.ingest_status == "processing":
            try:
                _dispatch_cognify_task(document_id, farm_id, plot_id, ocr_result.text)
                log.info("ingestion.cognify_dispatched", document_id=document_id, confidence=ocr_result.confidence)
            except Exception as exc:
                doc.ingest_status = "ingest_failed"
                doc.ingest_error = "Document was saved, but the processing job could not be queued. Retry the upload or contact support."
                await db.commit()
                await set_ingest_status(document_id, "ingest_failed", doc.ingest_error)
                log.error("ingestion.dispatch_failed", document_id=document_id, error=str(exc))
        await invalidate_query_cache(farm_id)
        return doc

    except Exception as exc:
        log.error("ingestion.saga_failed", document_id=document_id, error=str(exc), exc_info=True)
        doc.ingest_status = "ingest_failed"
        doc.ingest_error = "Document processing failed. Retry the upload or contact support."
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("ingestion.failure_state_commit_failed", document_id=document_id)
        await set_ingest_status(document_id, "ingest_failed", doc.ingest_error)
        raise


async def approve_document(db: AsyncSession, document_id: str, farm_id: str) -> Document:
    """
    Human reviewer approves a pending_review document.
    Dispatches the Cognify job and marks the document as processing.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.farm_id == farm_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise ValueError(f"Document {document_id} not found in farm {farm_id}")
    if doc.ingest_status != "pending_review":
        raise ValueError(f"Document {document_id} is not in pending_review state")

    doc.ingest_status = "processing"
    await set_ingest_status(document_id, "processing")
    await db.flush()
    await db.commit()
    try:
        _dispatch_cognify_task(document_id, farm_id, doc.plot_id, doc.extracted_text or "")
    except Exception as exc:
        doc.ingest_status = "pending_review"
        doc.ingest_error = "The processing job could not be queued. Retry approval or contact support."
        await db.commit()
        await set_ingest_status(document_id, "pending_review", doc.ingest_error)
        log.error("ingestion.approval_dispatch_failed", document_id=document_id, error=str(exc))
        raise RuntimeError("Document could not be queued for processing") from exc
    log.info("ingestion.approved_dispatched", document_id=document_id)
    return doc


async def reject_document(db: AsyncSession, document_id: str, farm_id: str, reason: str = "") -> Document:
    """Human reviewer rejects a pending_review document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.farm_id == farm_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    if doc.ingest_status != "pending_review":
        raise ValueError(f"Document {document_id} is not in pending_review state")
    doc.ingest_status = "ingest_failed"
    doc.ingest_error = f"Rejected by reviewer: {reason}"
    await set_ingest_status(document_id, "ingest_failed", doc.ingest_error)
    await db.flush()
    log.info("ingestion.rejected_by_reviewer", document_id=document_id)
    return doc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dispatch_cognify_task(document_id: str, farm_id: str, plot_id: str, text: str) -> None:
    celery_app.send_task(
        "app.workers.tasks.cognify_document",
        args=[document_id, farm_id, plot_id, text],
        queue="cognify",
        retry=True,
        retry_policy={"max_retries": 5, "interval_start": 2, "interval_step": 2, "interval_max": 30},
    )


def _guess_image_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")


def _passthrough_csv(content: bytes, filename: str) -> OCRResult:
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    
    # We must patch these properties onto the OCRResult or define it correctly.
    # Actually OCRResult has should_auto_ingest property which looks at confidence.
    # Since confidence is 1.0, should_auto_ingest is True, should_reject is False, needs_review is False.
    return OCRResult(text=text, confidence=1.0, provider="passthrough")
