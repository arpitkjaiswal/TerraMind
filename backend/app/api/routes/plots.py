"""
Plot (field) routes — CRUD for plots within an authenticated farm.

All routes enforce farm_id from the JWT — a user can only see/modify
plots belonging to their own farm.

GET    /api/v1/plots/              → list plots in farm
POST   /api/v1/plots/              → create plot
GET    /api/v1/plots/{plot_id}     → get plot details
PUT    /api/v1/plots/{plot_id}     → update plot
DELETE /api/v1/plots/{plot_id}     → delete plot (admin only)
GET    /api/v1/plots/{plot_id}/graph → get knowledge graph for plot
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.auth import get_current_token_data, TokenData, require_role
from app.core.database import get_db
from app.core.neo4j_client import temporal_subgraph
from app.models.db import Plot
from app.models.schemas import PlotCreate, PlotRead, PlotUpdate, GraphResponse

log = structlog.get_logger(__name__)
router = APIRouter()


async def _get_plot_or_404(plot_id: str, farm_id: str, db: AsyncSession) -> Plot:
    result = await db.execute(
        select(Plot).where(Plot.id == plot_id, Plot.farm_id == farm_id)
    )
    plot = result.scalar_one_or_none()
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
    return plot


@router.get("/", response_model=list[PlotRead])
async def list_plots(
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Plot).where(Plot.farm_id == td.farm_id))
    return result.scalars().all()


@router.post("/", response_model=PlotRead, status_code=201)
async def create_plot(
    body: PlotCreate,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    plot = Plot(
        id=str(uuid.uuid4()),
        farm_id=td.farm_id,
        name=body.name,
        crop_type=body.crop_type,
        size_ha=body.size_ha,
        geo_boundary=body.geo_boundary,
    )
    db.add(plot)
    await db.flush()
    log.info("plot.created", plot_id=plot.id, farm_id=td.farm_id)
    return plot


@router.get("/{plot_id}", response_model=PlotRead)
async def get_plot(
    plot_id: str,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    return await _get_plot_or_404(plot_id, td.farm_id, db)


@router.put("/{plot_id}", response_model=PlotRead)
async def update_plot(
    plot_id: str,
    body: PlotUpdate,
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    plot = await _get_plot_or_404(plot_id, td.farm_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(plot, field, value)
    await db.flush()
    return plot


@router.delete("/{plot_id}", status_code=204)
async def delete_plot(
    plot_id: str,
    td: TokenData = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    plot = await _get_plot_or_404(plot_id, td.farm_id, db)
    await db.delete(plot)
    log.info("plot.deleted", plot_id=plot_id, farm_id=td.farm_id)


@router.get("/{plot_id}/graph", response_model=GraphResponse)
async def get_plot_graph(
    plot_id: str,
    date_from: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    """Return the temporal knowledge graph subgraph for a plot."""
    await _get_plot_or_404(plot_id, td.farm_id, db)  # enforce ownership

    subgraph = await temporal_subgraph(
        plot_id=plot_id,
        farm_id=td.farm_id,
        date_from=date_from,
        date_to=date_to,
    )
    from app.models.schemas import GraphNode, GraphEdge
    nodes = [GraphNode(**n) for n in subgraph["nodes"]]
    edges = [GraphEdge(**e) for e in subgraph["edges"]]
    return GraphResponse(nodes=nodes, edges=edges, plot_id=plot_id, farm_id=td.farm_id)
