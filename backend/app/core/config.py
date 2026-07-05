"""
Application settings — loaded from environment variables / .env file.
All secrets are sourced from the environment; nothing is hard-coded here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "Aegis"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    ALLOWED_HOSTS: List[str] = ["*"]
    DEMO_MODE: bool = False

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # ── Postgres ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # asyncpg driver: postgresql+asyncpg://...

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str = "neo4j"

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_PREFIX: str = "aegis_"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL_SECONDS: int = 3600
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.92

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── S3 / Object storage ───────────────────────────────────────────────────
    S3_BUCKET: str = "aegis-documents"
    S3_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_ENDPOINT_URL: str = ""  # blank = AWS; set for MinIO

    # ── LLM ───────────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_PRIMARY: str = "anthropic"
    LLM_MODEL: str = "claude-3-5-sonnet-20241022"

    # ── OCR ───────────────────────────────────────────────────────────────────
    AZURE_FORM_RECOGNIZER_ENDPOINT: str = ""
    AZURE_FORM_RECOGNIZER_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    OCR_AUTO_INGEST_THRESHOLD: float = 0.85
    OCR_REJECT_THRESHOLD: float = 0.40

    # ── Cognee ────────────────────────────────────────────────────────────────
    COGNEE_LLM_PROVIDER: str = "anthropic"
    COGNEE_EMBEDDING_MODEL: str = "text-embedding-3-small"
    COGNEE_GRAPH_DATABASE_PROVIDER: str = "neo4j"
    COGNEE_VECTOR_DATABASE_PROVIDER: str = "qdrant"

    # ── Observability ─────────────────────────────────────────────────────────
    OTLP_ENDPOINT: str = "http://localhost:4317"
    SENTRY_DSN: str = ""
    PROMETHEUS_METRICS_ENABLED: bool = True

    # ── Rate limits ───────────────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_QUERY: str = "20/minute"
    RATE_LIMIT_INGEST: str = "10/minute"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # ── SSRF allow-list ───────────────────────────────────────────────────────
    ALLOWED_OUTBOUND_DOMAINS: List[str] = [
        "api.open-meteo.com",
        "openweathermap.org",
        "api.weather.gov",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @field_validator("ALLOWED_OUTBOUND_DOMAINS", mode="before")
    @classmethod
    def parse_domains(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()
