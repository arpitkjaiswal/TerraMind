"""
SQLAlchemy ORM models — PostgreSQL relational store.

Partitioned by farm_id at the application layer.
All tables include farm_id so queries always filter to a single tenant.

Saga pattern: Document.ingest_status tracks each step; a failed graph write
marks the document 'ingest_failed' rather than leaving it inconsistent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

UserRole = Enum("farmer", "agronomist", "admin", name="user_role")
SourceType = Enum("pdf", "photo", "csv", name="source_type")
IngestStatus = Enum(
    "pending_ocr", "pending_review", "processing", "ready", "ingest_failed",
    name="ingest_status",
)
ConfidenceLabel = Enum(
    "documented_fact", "statistical_association", "unconfirmed_hypothesis",
    name="confidence_label",
)
EdgeType = Enum(
    "APPLIED_TO", "OCCURRED_DURING", "PRECEDED", "CORRELATED_WITH", "CONFIRMED_CAUSE",
    name="edge_type",
)


# ── Models ────────────────────────────────────────────────────────────────────

class Farm(Base):
    __tablename__ = "farms"

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: str = Column(String(255), nullable=False)
    owner_user_id: str = Column(UUID(as_uuid=False), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    plots: List["Plot"] = relationship("Plot", back_populates="farm", cascade="all, delete-orphan")
    users: List["User"] = relationship("User", back_populates="farm", cascade="all, delete-orphan")


class Plot(Base):
    __tablename__ = "plots"
    __table_args__ = (
        Index("ix_plots_farm_created", "farm_id", "created_at"),
    )

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    farm_id: str = Column(UUID(as_uuid=False), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    name: str = Column(String(255), nullable=False)
    geo_boundary: Optional[str] = Column(Text, nullable=True)  # GeoJSON string
    crop_type: str = Column(String(255), nullable=False)
    size_ha: float = Column(Float, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    farm: "Farm" = relationship("Farm", back_populates="plots")
    documents: List["Document"] = relationship("Document", back_populates="plot", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    farm_id: str = Column(UUID(as_uuid=False), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    email: str = Column(String(320), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String(255), nullable=False)
    role: str = Column(UserRole, nullable=False, default="farmer")
    auth_provider_id: Optional[str] = Column(String(255), nullable=True)  # OAuth sub
    is_active: bool = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_now, nullable=False)
    last_login_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    farm: "Farm" = relationship("Farm", back_populates="users")
    queries: List["QueryLog"] = relationship("QueryLog", back_populates="user")
    corrections: List["Correction"] = relationship("Correction", back_populates="corrected_by")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_plot_created", "plot_id", "uploaded_at"),
        Index("ix_documents_farm_status", "farm_id", "ingest_status"),
    )

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    farm_id: str = Column(UUID(as_uuid=False), nullable=False)           # denormalised for fast per-farm queries
    plot_id: str = Column(UUID(as_uuid=False), ForeignKey("plots.id", ondelete="CASCADE"), nullable=False)
    source_type: str = Column(SourceType, nullable=False)
    label: str = Column(String(512), nullable=False)
    storage_uri: str = Column(String(1024), nullable=False)              # S3 object key
    content_hash: str = Column(String(64), nullable=True, index=True)   # SHA-256 for idempotency
    ingest_status: str = Column(IngestStatus, nullable=False, default="pending_ocr")
    ingest_error: Optional[str] = Column(Text, nullable=True)
    source_confidence: Optional[float] = Column(Float, nullable=True)   # OCR confidence
    extracted_text: Optional[str] = Column(Text, nullable=True)          # raw OCR output
    date_of_event: Optional[str] = Column(String(10), nullable=True)    # YYYY-MM-DD
    doc_metadata: Optional[dict] = Column("metadata", JSON, nullable=True)              # arbitrary extra fields
    uploaded_at: datetime = Column(DateTime(timezone=True), default=_now, nullable=False)
    processed_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    plot: "Plot" = relationship("Plot", back_populates="documents")
    evidence_edges: List["EvidenceEdge"] = relationship("EvidenceEdge", back_populates="source_document")


class QueryLog(Base):
    """
    Every user query is persisted here — enables audit trail,
    latency analytics, and evaluation harness.
    """
    __tablename__ = "query_logs"
    __table_args__ = (
        Index("ix_queries_plot_created", "plot_id", "created_at"),
        Index("ix_queries_farm_created", "farm_id", "created_at"),
    )

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    farm_id: str = Column(UUID(as_uuid=False), nullable=False)
    plot_id: str = Column(UUID(as_uuid=False), ForeignKey("plots.id", ondelete="SET NULL"), nullable=True)
    user_id: str = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    query_text: str = Column(Text, nullable=False)
    answer_text: Optional[str] = Column(Text, nullable=True)
    confidence_label: Optional[str] = Column(ConfidenceLabel, nullable=True)
    confidence_score: Optional[float] = Column(Float, nullable=True)
    graph_hops: Optional[int] = Column(Integer, nullable=True)
    latency_ms: Optional[int] = Column(Integer, nullable=True)
    cache_hit: bool = Column(Boolean, default=False, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_now, nullable=False)

    user: Optional["User"] = relationship("User", back_populates="queries")
    evidence_edges: List["EvidenceEdge"] = relationship("EvidenceEdge", back_populates="query")


class EvidenceEdge(Base):
    """
    Links a query answer to a specific graph node and source document.
    Every claim in an answer must trace to a row here — no traceable
    edge → claim is suppressed (hallucination mitigation).
    """
    __tablename__ = "evidence_edges"

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    query_id: str = Column(UUID(as_uuid=False), ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False)
    source_document_id: str = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    graph_node_id: str = Column(String(255), nullable=False)
    node_label: str = Column(String(512), nullable=False)
    node_type: str = Column(String(64), nullable=False)
    relationship_type: str = Column(EdgeType, nullable=False)
    date: Optional[str] = Column(String(10), nullable=True)

    query: "QueryLog" = relationship("QueryLog", back_populates="evidence_edges")
    source_document: Optional["Document"] = relationship("Document", back_populates="evidence_edges")
    corrections: List["Correction"] = relationship("Correction", back_populates="evidence_edge")


class Correction(Base):
    """
    Agronomist corrections to the evidence trail.
    Each correction triggers a memify() cycle on the next scheduled batch.
    """
    __tablename__ = "corrections"

    id: str = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    evidence_edge_id: str = Column(UUID(as_uuid=False), ForeignKey("evidence_edges.id", ondelete="CASCADE"), nullable=False)
    corrected_by_user_id: str = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    correction_note: str = Column(Text, nullable=False)
    memify_queued: bool = Column(Boolean, default=False, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_now, nullable=False)

    evidence_edge: "EvidenceEdge" = relationship("EvidenceEdge", back_populates="corrections")
    corrected_by: Optional["User"] = relationship("User", back_populates="corrections")
