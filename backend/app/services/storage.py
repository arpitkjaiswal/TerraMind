"""
Object storage service (S3-compatible).

Handles:
  - Raw document upload (idempotent by content_hash)
  - Presigned URL generation for frontend download/preview
  - SSRF protection: only allow-listed domains are fetched outbound
"""

from __future__ import annotations

import hashlib
import mimetypes
from typing import Optional, Tuple
from urllib.parse import urlparse

import aioboto3
import structlog

from app.core.config import settings
from app.core.circuit_breaker import ingestion_retry

log = structlog.get_logger(__name__)

_session = aioboto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    region_name=settings.S3_REGION,
)


def _s3_kwargs() -> dict:
    kwargs = {"service_name": "s3"}
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return kwargs


def compute_content_hash(content: bytes) -> str:
    """SHA-256 hex digest — used as idempotency key for uploads."""
    return hashlib.sha256(content).hexdigest()


def _object_key(farm_id: str, plot_id: str, document_id: str, filename: str) -> str:
    return f"{farm_id}/{plot_id}/{document_id}/{filename}"


@ingestion_retry
async def upload_document(
    farm_id: str,
    plot_id: str,
    document_id: str,
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Upload raw document bytes to S3.
    Returns (storage_uri, content_hash).
    Idempotent: if the content_hash already exists as a tag on the object,
    the upload is skipped and the existing key is returned.
    """
    key = _object_key(farm_id, plot_id, document_id, filename)
    content_hash = compute_content_hash(content)
    detected_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    async with _session.client(**_s3_kwargs()) as s3:
        # Check for existing object by content hash tag
        try:
            existing_tags = await s3.get_object_tagging(Bucket=settings.S3_BUCKET, Key=key)
            for tag in existing_tags.get("TagSet", []):
                if tag["Key"] == "content_hash" and tag["Value"] == content_hash:
                    log.info("storage.upload_skipped_duplicate", key=key)
                    return key, content_hash
        except s3.exceptions.NoSuchKey:
            pass

        await s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=content,
            ContentType=detected_type,
            Tagging=f"farm_id={farm_id}&content_hash={content_hash}",
            ServerSideEncryption="AES256",
        )
        log.info("storage.uploaded", key=key, bytes=len(content))

    return key, content_hash


async def generate_presigned_url(storage_uri: str, expires_in: int = 3600) -> str:
    """Generate a presigned GET URL for viewing a stored document."""
    async with _session.client(**_s3_kwargs()) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": storage_uri},
            ExpiresIn=expires_in,
        )
    return url


def validate_outbound_url(url: str) -> str:
    """
    SSRF protection: validate that an outbound URL is in the allow-list.
    Raises ValueError if not.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.split(":")[0].lower()
    allowed = settings.ALLOWED_OUTBOUND_DOMAINS
    if not any(domain == a or domain.endswith(f".{a}") for a in allowed):
        raise ValueError(f"Outbound domain '{domain}' not in allow-list: {allowed}")
    return url
