"""
Neo4j async driver singleton.

Provides a single driver instance reused across the app lifetime.
All graph operations use async sessions.

Node labels used in the agronomic ontology:
  Field | ChemicalProduct | WeatherEvent | CropVariant | YieldMeasurement | Practice

Edge types:
  APPLIED_TO | OCCURRED_DURING | PRECEDED | CORRELATED_WITH | CONFIRMED_CAUSE
  (CAUSED edges require explicit agronomist confirmation — never auto-asserted)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from neo4j import AsyncGraphDatabase
from app.core.config import settings
log = structlog.get_logger(__name__)
# Module-level singleton
neo4j_driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    max_connection_pool_size=50,
)

# ── Schema bootstrap ──────────────────────────────────────────────────────────

SCHEMA_QUERIES = [
    # Node indexes for fast temporal traversal
    "CREATE INDEX field_id IF NOT EXISTS FOR (n:Field) ON (n.id)",
    "CREATE INDEX chemical_id IF NOT EXISTS FOR (n:ChemicalProduct) ON (n.id)",
    "CREATE INDEX weather_date IF NOT EXISTS FOR (n:WeatherEvent) ON (n.date)",
    "CREATE INDEX yield_date IF NOT EXISTS FOR (n:YieldMeasurement) ON (n.date)",
    "CREATE INDEX practice_id IF NOT EXISTS FOR (n:Practice) ON (n.id)",
    "CREATE INDEX crop_id IF NOT EXISTS FOR (n:CropVariant) ON (n.id)",
    # Full-text search index
    "CREATE FULLTEXT INDEX entity_label IF NOT EXISTS FOR (n:Field|ChemicalProduct|WeatherEvent|CropVariant|YieldMeasurement|Practice) ON EACH [n.label, n.description]",
]


async def ensure_graph_schema() -> None:
    async with neo4j_driver.session(database=settings.NEO4J_DATABASE) as session:
        for q in SCHEMA_QUERIES:
            try:
                await session.run(q)
            except Exception as exc:
                log.warning("neo4j.schema_index_warning", query=q, error=str(exc))
    log.info("neo4j.schema_ready")


# ── Graph helpers ─────────────────────────────────────────────────────────────

async def run_read(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    async with neo4j_driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.run(query, params or {})
        return [dict(r) async for r in result]


async def run_write(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    async with neo4j_driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.run(query, params or {})
        return [dict(r) async for r in result]


async def upsert_node(
    label: str,
    node_id: str,
    properties: Dict[str, Any],
    farm_id: str,
    plot_id: str,
) -> None:
    """
    Merge a node by id (idempotent). Attaches farm_id and plot_id for
    tenant isolation — every graph node is scoped to a farm.
    """
    props = {**properties, "id": node_id, "farm_id": farm_id, "plot_id": plot_id}
    query = f"""
        MERGE (n:{label} {{id: $id}})
        SET n += $props
        RETURN n
    """
    await run_write(query, {"id": node_id, "props": props})


async def upsert_edge(
    source_id: str,
    target_id: str,
    rel_type: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Merge an edge between two nodes (idempotent by source+target+type)."""
    props = properties or {}
    query = f"""
        MATCH (a {{id: $src}}), (b {{id: $tgt}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN r
    """
    await run_write(query, {"src": source_id, "tgt": target_id, "props": props})


async def temporal_subgraph(
    plot_id: str,
    farm_id: str,
    max_hops: int = 4,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, List]:
    """
    Retrieve all nodes and edges for a plot, optionally filtered by date range.
    Used by the evidence layer to build the reasoning path.
    """
    where_clauses = ["n.farm_id = $farm_id", "n.plot_id = $plot_id"]
    if date_from:
        where_clauses.append("(n.date IS NULL OR n.date >= $date_from)")
    if date_to:
        where_clauses.append("(n.date IS NULL OR n.date <= $date_to)")
    where = " AND ".join(where_clauses)

    query = f"""
        MATCH (n)
        WHERE {where}
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m.farm_id = $farm_id
        RETURN
            collect(DISTINCT {{id: n.id, label: n.label, type: labels(n)[0], date: n.date, properties: properties(n)}}) AS nodes,
            collect(DISTINCT {{source: startNode(r).id, target: endNode(r).id, type: type(r), confirmed: r.confirmed}}) AS edges
    """
    params = {"farm_id": farm_id, "plot_id": plot_id}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    rows = await run_read(query, params)
    if not rows:
        return {"nodes": [], "edges": []}
    return {"nodes": rows[0].get("nodes", []), "edges": rows[0].get("edges", [])}


async def mark_edge_confirmed(
    source_id: str,
    target_id: str,
    rel_type: str,
    confirmed_by: str,
) -> None:
    """Agronomist confirms a causal edge — sets confirmed=true on the relationship."""
    query = f"""
        MATCH (a {{id: $src}})-[r:{rel_type}]->(b {{id: $tgt}})
        SET r.confirmed = true, r.confirmed_by = $confirmed_by, r.confirmed_at = datetime()
        RETURN r
    """
    await run_write(query, {"src": source_id, "tgt": target_id, "confirmed_by": confirmed_by})
