"""
OCR / Handwriting digitisation service.

Pipeline:
  1. Try Azure AI Document Intelligence (primary)
  2. Fall back to Google Cloud Vision if Azure fails or is unconfigured
  3. Return (extracted_text, confidence_score)
  4. confidence >= OCR_AUTO_INGEST_THRESHOLD → auto-ingest
  5. confidence in (OCR_REJECT_THRESHOLD, threshold) → human review queue
  6. confidence < OCR_REJECT_THRESHOLD → rejected, document marked ingest_failed

Every node derived from an OCR'd source keeps a link back to the original
scanned image via the Document.storage_uri field.
"""

from __future__ import annotations

import io

import structlog
from app.core.config import settings
from app.core.circuit_breaker import ocr_retry

log = structlog.get_logger(__name__)


class OCRResult:
    def __init__(self, text: str, confidence: float, provider: str):
        self.text = text
        self.confidence = confidence
        self.provider = provider

    @property
    def should_auto_ingest(self) -> bool:
        return self.confidence >= settings.OCR_AUTO_INGEST_THRESHOLD

    @property
    def should_reject(self) -> bool:
        return self.confidence < settings.OCR_REJECT_THRESHOLD

    @property
    def needs_review(self) -> bool:
        return not self.should_auto_ingest and not self.should_reject


# ── Azure AI Document Intelligence ────────────────────────────────────────────

@ocr_retry
async def _azure_ocr(image_bytes: bytes, content_type: str) -> OCRResult:
    """
    Use Azure AI Document Intelligence (Form Recognizer) for handwriting.
    Returns word-level confidence averaged across the document.
    """
    if not settings.AZURE_FORM_RECOGNIZER_ENDPOINT or not settings.AZURE_FORM_RECOGNIZER_KEY:
        raise ValueError("Azure Form Recognizer not configured")

    from azure.ai.formrecognizer.aio import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentAnalysisClient(
        endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
        credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_KEY),
    )
    async with client:
        poller = await client.begin_analyze_document(
            "prebuilt-read",
            document=io.BytesIO(image_bytes),
            content_type=content_type,
        )
        result = await poller.result()

    lines = []
    confidences = []
    for page in result.pages:
        for line in page.lines:
            lines.append(line.content)
        for word in page.words:
            if word.confidence is not None:
                confidences.append(word.confidence)

    text = "\n".join(lines)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
    log.info("ocr.azure_done", chars=len(text), confidence=round(avg_conf, 3))
    return OCRResult(text=text, confidence=avg_conf, provider="azure")


# ── Google Cloud Vision fallback ──────────────────────────────────────────────

@ocr_retry
async def _google_ocr(image_bytes: bytes) -> OCRResult:
    """
    Google Cloud Vision DOCUMENT_TEXT_DETECTION — better for dense text.
    Confidence is approximated from the full-text annotation.
    """
    import asyncio
    from google.cloud import vision

    def _sync_call():
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.document_text_detection(image=image)
        return response

    response = await asyncio.to_thread(_sync_call)
    if response.error.message:
        raise IOError(f"Google Vision error: {response.error.message}")

    full_text = response.full_text_annotation.text if response.full_text_annotation else ""
    # Google doesn't expose per-document confidence directly; approximate from word-level
    confidences = []
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for para in block.paragraphs:
                for word in para.words:
                    if word.confidence:
                        confidences.append(word.confidence)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
    log.info("ocr.google_done", chars=len(full_text), confidence=round(avg_conf, 3))
    return OCRResult(text=full_text, confidence=avg_conf, provider="google")


# ── Public interface ──────────────────────────────────────────────────────────

async def extract_text(image_bytes: bytes, content_type: str = "image/jpeg") -> OCRResult:
    """
    Main entry point. Tries Azure first, falls back to Google.
    A completely blank/corrupt image returns confidence=0 and triggers rejection.
    """
    try:
        return await _azure_ocr(image_bytes, content_type)
    except Exception as azure_err:
        log.warning("ocr.azure_failed_fallback_google", error=str(azure_err))

    try:
        return await _google_ocr(image_bytes)
    except Exception as google_err:
        log.error("ocr.all_providers_failed", error=str(google_err))
        return OCRResult(text="", confidence=0.0, provider="none")


async def extract_text_from_pdf(pdf_bytes: bytes) -> OCRResult:
    """
    Extract text from a digital PDF using pdfplumber (no OCR needed).
    Confidence is set to 1.0 for structured/digital PDFs.
    """
    import pdfplumber
    import io

    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

    full_text = "\n\n".join(pages)
    confidence = 1.0 if full_text.strip() else 0.0
    log.info("ocr.pdf_extracted", pages=len(pages), confidence=confidence)
    return OCRResult(text=full_text, confidence=confidence, provider="pdfplumber")
