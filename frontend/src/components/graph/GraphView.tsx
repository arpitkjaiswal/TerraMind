"use client";

import React, { useMemo, useRef, useState } from "react";
import type { PointerEvent, WheelEvent } from "react";
import type { GraphEdge, GraphNode } from "@/types";
import styles from "./GraphView.module.css";
import { Focus, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  Field: "#4ade80",
  ChemicalProduct: "#fbbf24",
  WeatherEvent: "#38bdf8",
  CropVariant: "#a3e635",
  YieldMeasurement: "#fb7185",
  Practice: "#fb923c",
};

const EDGE_COLORS: Record<string, string> = {
  APPLIED_TO: "#4ade80",
  OCCURRED_DURING: "#38bdf8",
  CORRELATED_WITH: "#fbbf24",
  CONFIRMED_CAUSE: "#fb7185",
  PRECEDED: "#a78bfa",
};

const WIDTH = 1000;
const HEIGHT = 620;
const CENTER = { x: WIDTH / 2, y: HEIGHT / 2 };
const colorForNode = (type: string) => NODE_COLORS[type] ?? "#94a3b8";
const colorForEdge = (type: string) => EDGE_COLORS[type] ?? "#94a3b8";

function hash(value: string) {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

/** A stable, dependency-free force layout so any live graph gets useful positions. */
function createLayout(nodes: GraphNode[], edges: GraphEdge[]) {
  const positions = new Map<string, { x: number; y: number }>();
  const count = nodes.length;
  if (!count) return positions;

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const degree = new Map(nodes.map((node) => [node.id, 0]));
  edges.forEach((edge) => {
    if (degree.has(edge.source)) degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    if (degree.has(edge.target)) degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });
  const radius = Math.min(245, Math.max(100, 42 * Math.sqrt(count)));
  const sorted = [...nodes].sort((a, b) => hash(a.id) - hash(b.id));

  sorted.forEach((node, index) => {
    if (node.type === "Field") {
      positions.set(node.id, { ...CENTER });
      return;
    }
    const angle = (index / Math.max(count - 1, 1)) * Math.PI * 2 + hash(node.id) % 37 / 100;
    const nodeRadius = radius * (0.72 + (hash(`${node.id}:r`) % 55) / 100);
    positions.set(node.id, {
      x: CENTER.x + Math.cos(angle) * nodeRadius,
      y: CENTER.y + Math.sin(angle) * nodeRadius * 0.72,
    });
  });

  const movable = nodes.filter((node) => node.type !== "Field");
  const iterations = Math.min(70, Math.max(22, count * 2));
  for (let step = 0; step < iterations; step += 1) {
    const forces = new Map(movable.map((node) => [node.id, { x: 0, y: 0 }]));
    for (let left = 0; left < movable.length; left += 1) {
      const a = movable[left];
      const pa = positions.get(a.id)!;
      for (let right = left + 1; right < movable.length; right += 1) {
        const b = movable[right];
        const pb = positions.get(b.id)!;
        const dx = pa.x - pb.x || 0.01;
        const dy = pa.y - pb.y || 0.01;
        const distanceSquared = Math.max(dx * dx + dy * dy, 36);
        const strength = 1450 / distanceSquared;
        const fx = (dx / Math.sqrt(distanceSquared)) * strength;
        const fy = (dy / Math.sqrt(distanceSquared)) * strength;
        forces.get(a.id)!.x += fx;
        forces.get(a.id)!.y += fy;
        forces.get(b.id)!.x -= fx;
        forces.get(b.id)!.y -= fy;
      }
    }
    edges.forEach((edge) => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.max(Math.hypot(dx, dy), 1);
      const desired = edge.type === "APPLIED_TO" ? 170 : 205;
      const pull = (distance - desired) * 0.0025;
      const force = { x: (dx / distance) * pull, y: (dy / distance) * pull };
      const sourceForce = forces.get(edge.source);
      const targetForce = forces.get(edge.target);
      if (sourceForce) { sourceForce.x += force.x; sourceForce.y += force.y; }
      if (targetForce) { targetForce.x -= force.x; targetForce.y -= force.y; }
    });
    movable.forEach((node) => {
      const point = positions.get(node.id)!;
      const force = forces.get(node.id)!;
      const centerPull = nodeById.get(node.id)?.type === "Field" ? 0 : 0.0015;
      point.x += Math.max(-7, Math.min(7, force.x - (point.x - CENTER.x) * centerPull));
      point.y += Math.max(-7, Math.min(7, force.y - (point.y - CENTER.y) * centerPull));
      point.x = Math.max(75, Math.min(WIDTH - 75, point.x));
      point.y = Math.max(70, Math.min(HEIGHT - 75, point.y));
    });
  }

  return positions;
}

function readableLabel(label: string, max = 20) {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

export default function GraphView({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [confirmedOnly, setConfirmedOnly] = useState(false);
  const [labelsVisible, setLabelsVisible] = useState(true);

  const layout = useMemo(() => createLayout(nodes, edges), [nodes, edges]);
  const selected = nodes.find((node) => node.id === selectedId) ?? null;
  const types = [...new Set(nodes.map((node) => node.type))];
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matchesQuery = (node: GraphNode) => !normalizedQuery || `${node.label} ${node.type}`.toLocaleLowerCase().includes(normalizedQuery);
  const visibleByType = (node: GraphNode) => typeFilter === "all" || node.type === typeFilter;
  const visibleEdges = edges.filter((edge) => !confirmedOnly || edge.confirmed);
  const connectedIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedId) {
      ids.add(selectedId);
      visibleEdges.forEach((edge) => {
        if (edge.source === selectedId) ids.add(edge.target);
        if (edge.target === selectedId) ids.add(edge.source);
      });
    }
    return ids;
  }, [selectedId, visibleEdges]);
  const visibleNodeCount = nodes.filter((node) => visibleByType(node) && matchesQuery(node)).length;
  const getPoint = (id: string) => layout.get(id) ?? CENTER;

  function updateZoom(nextZoom: number, anchor?: { x: number; y: number }) {
    const bounded = Math.max(0.45, Math.min(nextZoom, 2.8));
    if (anchor) {
      const ratio = bounded / zoom;
      setPan((current) => ({
        x: anchor.x - (anchor.x - current.x) * ratio,
        y: anchor.y - (anchor.y - current.y) * ratio,
      }));
    }
    setZoom(bounded);
  }

  function onWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const point = { x: ((event.clientX - rect.left) / rect.width) * WIDTH, y: ((event.clientY - rect.top) / rect.height) * HEIGHT };
    updateZoom(zoom * (event.deltaY < 0 ? 1.12 : 0.89), point);
  }

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest("[data-graph-node]")) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragRef.current || dragRef.current.pointerId !== event.pointerId) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const scaleX = WIDTH / rect.width / zoom;
    const scaleY = HEIGHT / rect.height / zoom;
    setPan({
      x: dragRef.current.panX + (event.clientX - dragRef.current.x) * scaleX,
      y: dragRef.current.panY + (event.clientY - dragRef.current.y) * scaleY,
    });
  }

  function onPointerEnd(event: PointerEvent<SVGSVGElement>) {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
  }

  function fitGraph() {
    setPan({ x: 0, y: 0 });
    setZoom(1);
  }

  return (
    <section className={styles.container} aria-label="Knowledge graph">
      <header className={styles.header}>
        <div className={styles.headingBlock}>
          <div className={styles.eyebrow}><span className={styles.liveDot} /> FIELD INTELLIGENCE</div>
          <h1 className={styles.title}>Knowledge graph</h1>
          <p className={styles.subtitle}>Explore how your field records connect. Select a node to trace its evidence and relationships.</p>
        </div>
        <div className={styles.summary} aria-label="Graph summary">
          <div className={styles.stat}><strong>{nodes.length}</strong><span>entities</span></div>
          <span className={styles.statDivider} />
          <div className={styles.stat}><strong>{edges.length}</strong><span>relationships</span></div>
        </div>
      </header>

      <div className={styles.workspace}>
        <div className={styles.toolbar}>
          <label className={styles.searchBox}>
            <Search size={16} aria-hidden="true" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find an entity…" aria-label="Search entities" />
            {query && <button type="button" className={styles.clearSearch} onClick={() => setQuery("")} aria-label="Clear search">×</button>}
          </label>
          <label className={styles.filterLabel}>
            <span>Type</span>
            <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filter by entity type">
              <option value="all">All entities</option>
              {types.map((type) => <option key={type} value={type}>{type.replace(/([a-z])([A-Z])/g, "$1 $2")}</option>)}
            </select>
          </label>
          <div className={styles.toolbarSpacer} />
          <span className={styles.resultCount}>{visibleNodeCount} of {nodes.length} shown</span>
          <div className={styles.controlGroup} aria-label="Graph controls">
            <button type="button" className={styles.controlBtn} onClick={() => updateZoom(zoom / 1.2)} title="Zoom out" aria-label="Zoom out"><ZoomOut size={16} /></button>
            <span className={styles.zoomValue}>{Math.round(zoom * 100)}%</span>
            <button type="button" className={styles.controlBtn} onClick={() => updateZoom(zoom * 1.2)} title="Zoom in" aria-label="Zoom in"><ZoomIn size={16} /></button>
            <button type="button" className={styles.controlBtn} onClick={fitGraph} title="Fit graph" aria-label="Fit graph"><Focus size={16} /></button>
            <button type="button" className={styles.controlBtn} onClick={() => { fitGraph(); setSelectedId(null); setQuery(""); setTypeFilter("all"); setConfirmedOnly(false); }} title="Reset view" aria-label="Reset graph view"><RotateCcw size={15} /></button>
          </div>
        </div>

        <div className={styles.canvas}>
          <div className={styles.canvasGlow} aria-hidden="true" />
          <div className={styles.canvasHint}><span className={styles.hintKey}>DRAG</span> to move <span className={styles.hintDivider}>·</span> scroll to zoom</div>
          {nodes.length === 0 ? (
            <div className={styles.emptyState}><div className={styles.emptyIcon}>✳</div><h2>Your field graph is ready to grow</h2><p>Add or process a field record and its entities will appear here.</p></div>
          ) : (
            <svg
              ref={svgRef}
              className={styles.svg}
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              role="img"
              aria-label={`Interactive knowledge graph with ${nodes.length} entities and ${edges.length} relationships`}
              onWheel={onWheel}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerEnd}
              onPointerCancel={onPointerEnd}
            >
              <defs>
                <pattern id="graph-grid" width="38" height="38" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="1" fill="rgba(148,163,184,.17)" />
                </pattern>
                <filter id="node-glow" x="-100%" y="-100%" width="300%" height="300%">
                  <feGaussianBlur stdDeviation="5" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                {Object.entries(EDGE_COLORS).map(([type, color]) => (
                  <marker key={type} id={`graph-arrow-${type}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                    <path d="M0,0 L8,4 L0,8 z" fill={color} />
                  </marker>
                ))}
                <marker id="graph-arrow-default" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                  <path d="M0,0 L8,4 L0,8 z" fill="#94a3b8" />
                </marker>
              </defs>
              <rect width={WIDTH} height={HEIGHT} fill="url(#graph-grid)" />
              <g transform={`translate(${CENTER.x + pan.x} ${CENTER.y + pan.y}) scale(${zoom}) translate(${-CENTER.x} ${-CENTER.y})`}>
                {visibleEdges.map((edge) => {
                  const source = getPoint(edge.source);
                  const target = getPoint(edge.target);
                  const sourceNode = nodes.find((node) => node.id === edge.source);
                  const targetNode = nodes.find((node) => node.id === edge.target);
                  const active = selectedId ? connectedIds.has(edge.source) && connectedIds.has(edge.target) : hoveredId === edge.source || hoveredId === edge.target;
                  const dimmed = (normalizedQuery.length > 0 && !!sourceNode && !!targetNode && !matchesQuery(sourceNode) && !matchesQuery(targetNode))
                    || (typeFilter !== "all" && sourceNode?.type !== typeFilter && targetNode?.type !== typeFilter)
                    || (!!selectedId && !active);
                  const color = colorForEdge(edge.type);
                  const marker = EDGE_COLORS[edge.type] ? `url(#graph-arrow-${edge.type})` : "url(#graph-arrow-default)";
                  return (
                    <g key={edge.id} className={styles.edge} opacity={dimmed ? 0.08 : active ? 0.95 : 0.46}>
                      <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke={color} strokeWidth={active ? 2.6 : 1.6} strokeDasharray={edge.confirmed ? undefined : "6 6"} markerEnd={marker} />
                      {labelsVisible && (active || (!selectedId && !normalizedQuery && edges.length <= 14)) && (
                        <g transform={`translate(${(source.x + target.x) / 2}, ${(source.y + target.y) / 2})`}>
                          <rect x="-52" y="-12" width="104" height="18" rx="9" fill="#101821" stroke="rgba(255,255,255,.08)" />
                          <text textAnchor="middle" y="1" fill={color} fontSize="8" fontWeight="700" letterSpacing=".7">{edge.type.replaceAll("_", " ")}</text>
                        </g>
                      )}
                    </g>
                  );
                })}
                {nodes.map((node) => {
                  const point = getPoint(node.id);
                  const color = colorForNode(node.type);
                  const isSelected = selectedId === node.id;
                  const isHovered = hoveredId === node.id;
                  const isMatch = matchesQuery(node) && visibleByType(node);
                  const isNeighbor = connectedIds.has(node.id);
                  const faded = !isMatch || (!!selectedId && !isNeighbor && !isSelected);
                  const radius = node.type === "Field" ? 35 : Math.min(31, 22 + Math.sqrt((degreeFor(node.id, edges))) * 2.5);
                  return (
                    <g
                      key={node.id}
                      data-graph-node="true"
                      transform={`translate(${point.x} ${point.y})`}
                      className={styles.node}
                      opacity={faded ? 0.22 : 1}
                      role="button"
                      tabIndex={0}
                      aria-label={`${node.label}, ${node.type}`}
                      aria-pressed={isSelected}
                      onClick={(event) => { event.stopPropagation(); setSelectedId(isSelected ? null : node.id); }}
                      onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(isSelected ? null : node.id); } }}
                      onMouseEnter={() => setHoveredId(node.id)}
                      onMouseLeave={() => setHoveredId(null)}
                    >
                      {(isSelected || isHovered) && <circle r={radius + 12} fill={color} opacity=".08" filter="url(#node-glow)" />}
                      <circle r={radius + 6} fill="none" stroke={color} strokeWidth="1" opacity={isSelected ? ".62" : isHovered ? ".4" : ".12"} />
                      <circle r={radius} fill={node.type === "Field" ? "#173426" : "#111b25"} stroke={color} strokeWidth={isSelected ? 2.5 : isHovered ? 2 : 1.4} />
                      <circle cx={radius * 0.66} cy={-radius * 0.66} r="3.5" fill={color} />
                      <text y="1" textAnchor="middle" dominantBaseline="middle" fill="#edf5f3" fontSize={node.type === "Field" ? 10 : 9} fontWeight="700" pointerEvents="none">
                        {readableLabel(node.label, node.type === "Field" ? 16 : 13)}
                      </text>
                      <text y={radius + 17} textAnchor="middle" fill="#98a8b7" fontSize="9" fontWeight="600" letterSpacing=".5" pointerEvents="none">
                        {node.type.replace(/([a-z])([A-Z])/g, "$1 $2").toUpperCase()}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          )}
          <div className={styles.canvasFooter}>
            <button type="button" className={`${styles.toggle} ${confirmedOnly ? styles.toggleActive : ""}`} onClick={() => setConfirmedOnly((value) => !value)} aria-pressed={confirmedOnly}>
              <span className={styles.toggleTrack}><span /></span> Confirmed only
            </button>
            <span className={styles.footerDivider} />
            <button type="button" className={`${styles.toggle} ${labelsVisible ? styles.toggleActive : ""}`} onClick={() => setLabelsVisible((value) => !value)} aria-pressed={labelsVisible}>Relationship labels</button>
            <div className={styles.legendInline}>
              <span><i className={styles.confirmedLine} />Confirmed</span>
              <span><i className={styles.uncertainLine} />Needs review</span>
            </div>
          </div>
        </div>
      </div>

      {selected && (
        <aside className={`${styles.inspector} animate-slide-left`} aria-label="Selected entity details">
          <div className={styles.inspectorHeader}>
            <div className={styles.inspectorIcon} style={{ color: colorForNode(selected.type), borderColor: `${colorForNode(selected.type)}55`, background: `${colorForNode(selected.type)}12` }}>✳</div>
            <div className={styles.inspectorHeading}>
              <span className={styles.inspectorType} style={{ color: colorForNode(selected.type) }}>{selected.type.replace(/([a-z])([A-Z])/g, "$1 $2")}</span>
              <h2 className={styles.inspectorLabel}>{selected.label}</h2>
            </div>
            <button type="button" className={styles.closeInspector} onClick={() => setSelectedId(null)} aria-label="Close entity details">×</button>
          </div>
          {selected.date && <div className={styles.inspectorDate}>RECORDED <strong>{selected.date}</strong></div>}
          {Object.keys(selected.properties).length > 0 && (
            <div className={styles.inspectorProps}>
              <h3>Entity details</h3>
              {Object.entries(selected.properties).map(([key, value]) => (
                <div key={key} className={styles.propRow}><span>{key.replaceAll("_", " ")}</span><strong>{String(value)}</strong></div>
              ))}
            </div>
          )}
          <div className={styles.inspectorEdges}>
            <h3>Connected evidence <span>{edges.filter((edge) => edge.source === selected.id || edge.target === selected.id).length}</span></h3>
            {edges.filter((edge) => edge.source === selected.id || edge.target === selected.id).length === 0 ? (
              <p className={styles.noConnections}>No relationships recorded for this entity yet.</p>
            ) : edges.filter((edge) => edge.source === selected.id || edge.target === selected.id).map((edge) => {
              const other = nodes.find((node) => node.id === (edge.source === selected.id ? edge.target : edge.source));
              return (
                <button key={edge.id} className={styles.edgeRow} onClick={() => other && setSelectedId(other.id)} type="button">
                  <span className={styles.edgePip} style={{ background: colorForEdge(edge.type) }} />
                  <span className={styles.edgeContent}><strong>{other?.label ?? "Unknown entity"}</strong><small>{edge.type.replaceAll("_", " ")}</small></span>
                  <span className={`${styles.statusBadge} ${edge.confirmed ? styles.confirmed : styles.review}`}>{edge.confirmed ? "Verified" : "Review"}</span>
                </button>
              );
            })}
          </div>
        </aside>
      )}
    </section>
  );
}

function degreeFor(id: string, edges: GraphEdge[]) {
  return edges.reduce((sum, edge) => sum + Number(edge.source === id || edge.target === id), 0);
}
