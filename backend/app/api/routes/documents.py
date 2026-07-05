"""
Document ingestion routes.

POST /api/v1/documents/upload          → upload file (raw binary)
GET  /api/v1/documents/                → list documents for a plot
GET  /api/v1/documents/{id}            → get document details
GET  /api/v1/documents/{id}/url        → get presigned download URL
GET  /api/v1/documents/review-queue    → list pending_review documents
POST /api/v1/documents/{id}/approve    → approve OCR result
POST /api/v1/documents/{id}/reject     → reject OCR result
GET  /api/v1/documents/{id}/status     → polling endpoint for ingest status
"""

from typing import Optional
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_token_data, TokenData, require_role
from app.core.database import get_db
from app.core.redis_client import get_ingest_status
from app.models.db import Document
from app.models.schemas import (
    DocumentIngestResponse,
    DocumentRead,
    ReviewDecision,
    ReviewQueueItem,
)
from app.services.ingestion import (
    approve_document,
    ingest_document,
    reject_document,
)
from app.services.storage import generate_presigned_url

log = structlog.get_logger(__name__)
router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", response_model=DocumentIngestResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    plot_id: str = Form(...),
    label: str = Form(...),
    date_of_event: Optional[str] = Form(default=None),
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts raw file upload. Determines source_type from content type.
    Returns immediately with document_id; ingestion runs async via Celery.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // 1024 // 1024} MB)")

    filename = file.filename or "upload"
    content_type = file.content_type or ""
    source_type = _detect_source_type(filename, content_type)

    doc = await ingest_document(
        db=db,
        farm_id=td.farm_id,
        plot_id=plot_id,
        filename=filename,
        content=content,
        source_type=source_type,
        label=label,
        date_of_event=date_of_event,
    )

    msg_map = {
        "processing":     "Document auto-ingested (high confidence OCR) — graph processing queued.",
        "pending_review": "Document queued for human review (OCR confidence below threshold).",
        "ingest_failed":  "Document ingestion failed — see error details.",
    }
    return DocumentIngestResponse(
        document_id=doc.id,
        ingest_status=doc.ingest_status,
        source_confidence=doc.source_confidence,
        message=msg_map.get(doc.ingest_status, doc.ingest_status),
    )


@router.get("/", response_model=list[DocumentRead])
async def list_documents(
    plot_id: Optional[str] = Query(default=None),
    ingest_status: Optional[str] = Query(default=None),
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    query = select(Document).where(Document.farm_id == td.farm_id)
    if plot_id:
        query = query.where(Document.plot_id == plot_id)
    if ingest_status:
        query = query.where(Document.ingest_status == ingest_status)
    query = query.order_by(Document.uploaded_at.desc())  # type: ignore[attr-defined]
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/review-queue", response_model=list[ReviewQueueItem])
async def get_review_queue(
    td: TokenData = Depends(require_role("admin", "agronomist")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.farm_id == td.farm_id, Document.ingest_status == "pending_review")
        .order_by(Document.uploaded_at.asc())  # type: ignore[attr-defined]
    )
    docs = result.scalars().all()
    return [
        ReviewQueueItem(
            document_id=d.id,
            label=d.label,
            source_type=d.source_type,
            source_confidence=d.source_confidence or 0.0,
            extracted_text=d.extracted_text or "",
            uploaded_at=d.uploaded_at,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.farm_id == td.farm_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/url")
async def get_document_url(
    document_id: str,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.farm_id == td.farm_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    url = await generate_presigned_url(doc.storage_uri)
    return {"url": url, "expires_in": 3600}


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    """Polling endpoint — check ingest progress without a full document fetch."""
    redis_status = await get_ingest_status(document_id)
    if redis_status:
        return redis_status
    result = await db.execute(
        select(Document.ingest_status, Document.ingest_error)
        .where(Document.id == document_id, Document.farm_id == td.farm_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": row[0], "detail": row[1] or ""}


@router.post("/{document_id}/approve", response_model=DocumentRead)
async def approve(
    document_id: str,
    body: ReviewDecision,
    td: TokenData = Depends(require_role("admin", "agronomist")),
    db: AsyncSession = Depends(get_db),
):
    if body.action != "approve":
        raise HTTPException(status_code=400, detail="Use /reject endpoint for rejection")
    doc = await approve_document(db, document_id, td.farm_id)
    log.info("document.approved", document_id=document_id, user=td.user_id)
    return doc


@router.post("/{document_id}/reject", response_model=DocumentRead)
async def reject(
    document_id: str,
    body: ReviewDecision,
    td: TokenData = Depends(require_role("admin", "agronomist")),
    db: AsyncSession = Depends(get_db),
):
    doc = await reject_document(db, document_id, td.farm_id, reason=body.note or "")
    log.info("document.rejected", document_id=document_id, user=td.user_id)
    return doc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_source_type(filename: str, content_type: str) -> str:
    if "pdf" in content_type or filename.lower().endswith(".pdf"):
        return "pdf"
    if content_type.startswith("image/") or any(
        filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".tiff", ".webp"]
    ):
        return "photo"
    return "csv"
