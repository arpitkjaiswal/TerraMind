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

NODE_LABELS = frozenset({"Field", "ChemicalProduct", "WeatherEvent", "CropVariant", "YieldMeasurement", "Practice"})
RELATIONSHIP_TYPES = frozenset({"APPLIED_TO", "OCCURRED_DURING", "PRECEDED", "CORRELATED_WITH", "CONFIRMED_CAUSE"})


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
    if label not in NODE_LABELS:
        raise ValueError("Unsupported graph node label")
    props = {**properties, "id": node_id, "farm_id": farm_id, "plot_id": plot_id}
    query = f"""
        MERGE (n:{label} {{id: $id, farm_id: $farm_id, plot_id: $plot_id}})
        SET n += $props
        RETURN n
    """
    await run_write(query, {"id": node_id, "farm_id": farm_id, "plot_id": plot_id, "props": props})


async def upsert_edge(
    source_id: str,
    target_id: str,
    rel_type: str,
    farm_id: str,
    plot_id: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Merge an edge only between nodes belonging to the same farm and plot."""
    if rel_type not in RELATIONSHIP_TYPES:
        raise ValueError("Unsupported graph relationship type")
    props = properties or {}
    query = f"""
        MATCH (a {{id: $src, farm_id: $farm_id, plot_id: $plot_id}}),
              (b {{id: $tgt, farm_id: $farm_id, plot_id: $plot_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN r
    """
    await run_write(query, {"src": source_id, "tgt": target_id, "farm_id": farm_id, "plot_id": plot_id, "props": props})


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
    where_clauses = ["n.farm_id = $farm_id", "n.plot_id = $plot_id", "n.id IS NOT NULL"]
    if date_from:
        where_clauses.append("(n.date IS NULL OR toString(n.date) >= $date_from)")
    if date_to:
        where_clauses.append("(n.date IS NULL OR toString(n.date) <= $date_to)")
    where = " AND ".join(where_clauses)

    query = f"""
        MATCH (n)
        WHERE {where}
        WITH collect(n) AS scoped_nodes
        UNWIND scoped_nodes AS n
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m IN scoped_nodes
          AND ($date_from IS NULL OR r.date IS NULL OR toString(r.date) >= $date_from)
          AND ($date_to IS NULL OR r.date IS NULL OR toString(r.date) <= $date_to)
        RETURN
            collect(DISTINCT {{id: n.id, label: coalesce(n.label, n.id), type: labels(n)[0], date: toString(n.date), properties: properties(n)}}) AS nodes,
            collect(DISTINCT CASE WHEN r IS NOT NULL THEN {{
                source: startNode(r).id, target: endNode(r).id, type: type(r),
                confirmed: coalesce(r.confirmed, false), date: toString(r.date),
                source_document_id: r.source_document_id
            }} END) AS edges
    """
    params = {"farm_id": farm_id, "plot_id": plot_id, "date_from": date_from, "date_to": date_to}

    rows = await run_read(query, params)
    if not rows:
        return {"nodes": [], "edges": []}
    return {"nodes": rows[0].get("nodes", []), "edges": rows[0].get("edges", [])}


async def mark_edge_confirmed(
    source_id: str,
    target_id: str,
    rel_type: str,
    confirmed_by: str,
    farm_id: str,
    plot_id: str,
) -> bool:
    """Promote a scoped correlation to a human-confirmed causal relationship."""
    if rel_type != "CORRELATED_WITH" or not source_id or not target_id:
        return False
    query = f"""
        MATCH (a {{id: $src, farm_id: $farm_id, plot_id: $plot_id}})-[r:CORRELATED_WITH]->
              (b {{id: $tgt, farm_id: $farm_id, plot_id: $plot_id}})
        WITH a, b, r, properties(r) AS old_properties
        DELETE r
        CREATE (a)-[confirmed:CONFIRMED_CAUSE]->(b)
        SET confirmed = old_properties,
            confirmed.confirmed = true,
            confirmed.confirmed_by = $confirmed_by,
            confirmed.confirmed_at = datetime()
        RETURN count(confirmed) > 0 AS updated
    """
    rows = await run_write(query, {"src": source_id, "tgt": target_id, "farm_id": farm_id, "plot_id": plot_id, "confirmed_by": confirmed_by})
    return bool(rows and rows[0].get("updated"))
