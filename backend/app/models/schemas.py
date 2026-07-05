"""
Pydantic v2 request / response schemas.

Strict on input (extra="forbid") so bad fields are rejected at the API boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Shared base ───────────────────────────────────────────────────────────────

class _StrictBase(BaseModel):
    model_config = {"extra": "forbid"}


class _ReadBase(BaseModel):
    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(_StrictBase):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(_StrictBase):
    refresh_token: str


# ── Farm ──────────────────────────────────────────────────────────────────────

class FarmCreate(_StrictBase):
    name: str = Field(min_length=1, max_length=255)


class FarmRead(_ReadBase):
    id: str
    name: str
    owner_user_id: str
    created_at: datetime


# ── Plot ──────────────────────────────────────────────────────────────────────

class PlotCreate(_StrictBase):
    name: str = Field(min_length=1, max_length=255)
    crop_type: str = Field(min_length=1, max_length=255)
    size_ha: float = Field(gt=0)
    geo_boundary: Optional[str] = None  # GeoJSON string


class PlotUpdate(_StrictBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    crop_type: Optional[str] = Field(default=None, min_length=1)
    size_ha: Optional[float] = Field(default=None, gt=0)
    geo_boundary: Optional[str] = None


class PlotRead(_ReadBase):
    id: str
    farm_id: str
    name: str
    crop_type: str
    size_ha: float
    geo_boundary: Optional[str]
    created_at: datetime


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(_StrictBase):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["farmer", "agronomist", "admin"] = "farmer"


class UserRead(_ReadBase):
    id: str
    farm_id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


# ── Document ──────────────────────────────────────────────────────────────────

class DocumentRead(_ReadBase):
    id: str
    plot_id: str
    farm_id: str
    source_type: str
    label: str
    storage_uri: str
    ingest_status: str
    source_confidence: Optional[float]
    date_of_event: Optional[str]
    uploaded_at: datetime
    processed_at: Optional[datetime]


class DocumentIngestResponse(BaseModel):
    document_id: str
    ingest_status: str
    source_confidence: Optional[float]
    message: str


class ReviewQueueItem(BaseModel):
    document_id: str
    label: str
    source_type: str
    source_confidence: float
    extracted_text: str
    uploaded_at: datetime


class ReviewDecision(_StrictBase):
    action: Literal["approve", "reject"]
    note: Optional[str] = None


# ── Evidence trail ────────────────────────────────────────────────────────────

class EvidenceEdgeRead(BaseModel):
    id: str
    graph_node_id: str
    node_label: str
    node_type: str
    relationship_type: str
    source_document_id: Optional[str]
    source_document_label: Optional[str]
    date: Optional[str]


# ── Query ─────────────────────────────────────────────────────────────────────

class QueryRequest(_StrictBase):
    query_text: str = Field(min_length=5, max_length=2000)
    plot_id: str
    date_from: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    include_hypotheses: bool = False  # unconfirmed hypotheses shown only on explicit request

    @model_validator(mode="after")
    def validate_dates(self) -> "QueryRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self


class QueryResponse(BaseModel):
    """
    Primary query response schema — the contract the frontend depends on.
    Every field is first-class; nothing is buried in metadata.
    """
    query_id: str
    query_text: str
    answer_text: str
    confidence_label: Literal["documented_fact", "statistical_association", "unconfirmed_hypothesis"]
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence_trail: List[EvidenceEdgeRead]
    graph_hops: int
    latency_ms: int
    cache_hit: bool
    created_at: datetime


class QueryListItem(BaseModel):
    query_id: str
    query_text: str
    confidence_label: str
    confidence_score: float
    latency_ms: int
    created_at: datetime


# ── Correction ────────────────────────────────────────────────────────────────

class CorrectionCreate(_StrictBase):
    evidence_edge_id: str
    correction_note: str = Field(min_length=10, max_length=2000)


class CorrectionRead(_ReadBase):
    id: str
    evidence_edge_id: str
    corrected_by_user_id: Optional[str]
    correction_note: str
    memify_queued: bool
    created_at: datetime


# ── Graph ─────────────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    date: Optional[str]
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    confirmed: bool
    date: Optional[str]
    source_document_id: Optional[str]


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    plot_id: str
    farm_id: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthCheck(BaseModel):
    status: str
    version: str
    services: Dict[str, str]
