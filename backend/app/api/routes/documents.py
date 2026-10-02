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

from app.core.auth import get_current_token_data, TokenData
from app.core.database import get_db
from app.core.redis_client import get_ingest_status
from app.models.db import Document, Plot
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
    plot = await db.scalar(select(Plot).where(Plot.id == plot_id, Plot.farm_id == td.farm_id))
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // 1024 // 1024} MB)")

    filename = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or len(filename) > 255:
        raise HTTPException(status_code=400, detail="Filename must be between 1 and 255 characters")
    if not label.strip() or len(label) > 512:
        raise HTTPException(status_code=422, detail="Label must be between 1 and 512 characters")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    content_type = file.content_type or ""
    try:
        source_type = _detect_source_type(filename, content_type, content)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

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
    td: TokenData = Depends(get_current_token_data),
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
    result = await db.execute(
        select(Document.ingest_status, Document.ingest_error)
        .where(Document.id == document_id, Document.farm_id == td.farm_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    redis_status = await get_ingest_status(document_id)
    if redis_status:
        return redis_status
    return {"status": row[0], "detail": row[1] or ""}


@router.post("/{document_id}/approve", response_model=DocumentRead)
async def approve(
    document_id: str,
    body: ReviewDecision,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    if body.action != "approve":
        raise HTTPException(status_code=400, detail="Use /reject endpoint for rejection")
    try:
        doc = await approve_document(db, document_id, td.farm_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    log.info("document.approved", document_id=document_id, user=td.user_id)
    return doc


@router.post("/{document_id}/reject", response_model=DocumentRead)
async def reject(
    document_id: str,
    body: ReviewDecision,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc = await reject_document(db, document_id, td.farm_id, reason=body.note or "")
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    log.info("document.rejected", document_id=document_id, user=td.user_id)
    return doc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_source_type(filename: str, content_type: str, content: bytes | None = None) -> str:
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == "pdf" or content_type.lower() == "application/pdf":
        if content is not None and not content.startswith(b"%PDF-"):
            raise ValueError("The uploaded file does not contain a valid PDF signature")
        return "pdf"
    image_signatures = {
        "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",),
        "png": (b"\x89PNG\r\n\x1a\n",), "tiff": (b"II*\x00", b"MM\x00*"),
        "tif": (b"II*\x00", b"MM\x00*"), "webp": (b"RIFF",),
    }
    if extension in image_signatures or content_type.lower().startswith("image/"):
        if extension not in image_signatures:
            raise ValueError("Supported photos are JPEG, PNG, TIFF, and WebP")
        if content is not None and not any(content.startswith(signature) for signature in image_signatures[extension]):
            raise ValueError("The uploaded file does not match its image file type")
        if extension == "webp" and content is not None and content[8:12] != b"WEBP":
            raise ValueError("The uploaded file does not contain a valid WebP signature")
        return "photo"
    if extension == "csv" or content_type.lower() in {"text/csv", "application/vnd.ms-excel"}:
        if content is not None:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError("CSV files must use UTF-8 encoding") from exc
            if "\x00" in text:
                raise ValueError("The uploaded file is not valid CSV text")
        return "csv"
    raise ValueError("Unsupported file type. Upload a PDF, CSV, JPEG, PNG, TIFF, or WebP file.")
