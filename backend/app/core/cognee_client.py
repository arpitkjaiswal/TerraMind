"""
Cognee integration layer.

Wraps the Cognee extract → cognify → search pipeline with:
  - Agronomic ontology constraints (fixed entity set)
  - Temporal tagging (temporal_cognify=True equivalent)
  - GRAPH_COMPLETION search mode
  - Error boundary: LLM provider outage → circuit breaker
"""

from __future__ import annotations
from typing import Any, Dict

import structlog
import cognee

from app.core.config import settings
from app.core.circuit_breaker import llm_circuit_breaker

log = structlog.get_logger(__name__)

# ── Agronomic ontology ────────────────────────────────────────────────────────
# Fixed entity set — keeps the graph clean rather than open-ended.
# Cognee's Cognify step is constrained to this set.

AGRONOMIC_ENTITY_TYPES = [
    "Field",
    "ChemicalProduct",
    "WeatherEvent",
    "CropVariant",
    "YieldMeasurement",
    "Practice",
]

AGRONOMIC_RELATIONSHIP_TYPES = [
    "APPLIED_TO",
    "OCCURRED_DURING",
    "PRECEDED",
    "CORRELATED_WITH",
    # Note: CONFIRMED_CAUSE is NEVER auto-asserted — only via agronomist confirmation
]

COGNEE_SYSTEM_PROMPT = """
You are an agronomic knowledge extraction engine.
Extract entities ONLY from the following fixed types:
  - Field (a specific plot of agricultural land)
  - ChemicalProduct (pesticide, herbicide, fertiliser, or other chemical input)
  - WeatherEvent (drought, flood, frost, heatwave, rainfall event)
  - CropVariant (a specific variety or hybrid of a crop species)
  - YieldMeasurement (a recorded yield metric with a value and unit)
  - Practice (an agronomic action: tillage, cover crop, irrigation, etc.)

Extract relationships ONLY from:
  - APPLIED_TO: a product or practice applied to a field
  - OCCURRED_DURING: a weather event occurring during a crop or treatment period
  - PRECEDED: one event preceding another in time
  - CORRELATED_WITH: a statistical co-occurrence across records (NOT a confirmed cause)

CRITICAL rules:
  1. Never assert a CAUSED relationship — that requires explicit human confirmation.
  2. Always capture the date of every event if mentioned.
  3. If a quantity, unit, or concentration is mentioned, capture it in entity properties.
  4. Do not invent entities not explicitly mentioned in the source text.
"""


# ── Initialisation ────────────────────────────────────────────────────────────

async def init_cognee() -> None:
    """Configure Cognee with the correct provider settings at startup."""
    cognee.config.set_llm_config({
        "provider": settings.COGNEE_LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "api_key": settings.ANTHROPIC_API_KEY if settings.LLM_PRIMARY == "anthropic" else settings.OPENAI_API_KEY,
    })
    cognee.config.set_embedding_config({
        "provider": "openai",
        "model": settings.COGNEE_EMBEDDING_MODEL,
        "api_key": settings.OPENAI_API_KEY,
    })
    cognee.config.set_graph_database_config({
        "provider": settings.COGNEE_GRAPH_DATABASE_PROVIDER,
        "url": settings.NEO4J_URI,
        "username": settings.NEO4J_USER,
        "password": settings.NEO4J_PASSWORD,
        "database": settings.NEO4J_DATABASE,
    })
    cognee.config.set_vector_database_config({
        "provider": settings.COGNEE_VECTOR_DATABASE_PROVIDER,
        "url": f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
        "api_key": settings.QDRANT_API_KEY or None,
    })
    log.info("cognee.configured")


# ── Pipeline steps ────────────────────────────────────────────────────────────

async def run_extract(text: str, dataset_name: str) -> None:
    """
    Step 1: Add text to Cognee's dataset (extract stage).
    Idempotent — Cognee deduplicates by content hash.
    """
    await cognee.add(text, dataset_name=dataset_name)
    log.info("cognee.extract_done", dataset=dataset_name, chars=len(text))


@llm_circuit_breaker
async def run_cognify(
    dataset_name: str,
    farm_id: str,
    plot_id: str,
    source_document_id: str,
) -> None:
    """
    Step 2: Cognify — extract entities/relationships into the graph.
    Applies the agronomic ontology system prompt and temporal tagging.
    Circuit-broken around the LLM call.
    """
    log.info("cognee.cognify_start", dataset=dataset_name)
    await cognee.cognify(
        datasets=[dataset_name],
        system_prompt=COGNEE_SYSTEM_PROMPT,
        entity_types=AGRONOMIC_ENTITY_TYPES,
        relationship_types=AGRONOMIC_RELATIONSHIP_TYPES,
        # Metadata propagated to every node/edge created
        metadata={
            "farm_id": farm_id,
            "plot_id": plot_id,
            "source_document_id": source_document_id,
        },
    )
    log.info("cognee.cognify_done", dataset=dataset_name)


@llm_circuit_breaker
async def run_search(
    query_text: str,
    farm_id: str,
    plot_id: str,
) -> Dict[str, Any]:
    """
    Step 3: GRAPH_COMPLETION search — combines vector similarity with
    multi-hop graph traversal and temporal filters.
    Returns Cognee's raw result which we then pass to the evidence layer.
    """
    log.info("cognee.search_start", farm_id=farm_id, plot_id=plot_id)
    result = await cognee.search(
        query=query_text,
        search_type="GRAPH_COMPLETION",
        filters={
            "farm_id": farm_id,
            "plot_id": plot_id,
        },
    )
    log.info("cognee.search_done", result_keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__)
    return result


async def run_memify(farm_id: str, plot_id: str) -> None:
    """
    Memify — scheduled batch that re-processes corrections and new data
    so the graph improves over time. Called by the Celery scheduler.
    """
    log.info("cognee.memify_start", farm_id=farm_id, plot_id=plot_id)
    await cognee.memify(
        filters={"farm_id": farm_id, "plot_id": plot_id},
        system_prompt=COGNEE_SYSTEM_PROMPT,
    )
    log.info("cognee.memify_done", farm_id=farm_id, plot_id=plot_id)
