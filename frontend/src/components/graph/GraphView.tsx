"use client";

import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { GraphEdge, GraphNode } from "@/types";
import { emptyFilters, filterGraph, fitCamera, seedParticles, tickParticles, zoomAt } from "@/lib/graph";
import type { Camera, Particle, Point } from "@/lib/graph";
import { Download, Focus, Pause, Play, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";
import styles from "./GraphView.module.css";

interface Props { nodes: GraphNode[]; edges: GraphEdge[]; }
const NODE_COLORS: Record<string, string> = { Field: "#4ade80", Document: "#c4b5fd", ChemicalProduct: "#fbbf24", WeatherEvent: "#38bdf8", CropVariant: "#a3e635", YieldMeasurement: "#fb7185", Practice: "#fb923c" };
const EDGE_COLORS: Record<string, string> = { HAS_DOCUMENT: "#c4b5fd", DOCUMENTS: "#94a3b8", APPLIED_TO: "#4ade80", OCCURRED_DURING: "#38bdf8", CORRELATED_WITH: "#fbbf24", CONFIRMED_CAUSE: "#fb7185", PRECEDED: "#a78bfa" };
const readable = (label: string, max = 22) => label.length > max ? `${label.slice(0, max - 1)}…` : label;
const humanize = (value: string) => value.replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2");
const radius = (node?: GraphNode) => node?.type === "Field" ? 32 : 25;

type Drag = { pointer: number; start: Point; pan: Point; node?: string; offset: Point; moved: boolean };

export default function GraphView({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const particles = useRef(new Map<string, Particle>());
  const drag = useRef<Drag | null>(null);
  const ignoreClick = useRef(false);
  const autoFit = useRef(true);
  const graphId = useId().replaceAll(":", "");
  const [size, setSize] = useState<Point>({ x: 1000, y: 620 });
  const [positions, setPositions] = useState(() => seedParticles(nodes, { x: 1000, y: 620 }));
  const [camera, setCamera] = useState<Camera>({ pan: { x: 0, y: 0 }, zoom: 1 });
  const [filters, setFilters] = useState(emptyFilters);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [labels, setLabels] = useState(true);
  const [paused, setPaused] = useState(false);
  const [revision, setRevision] = useState(0);
  const visible = useMemo(() => filterGraph(nodes, edges, filters), [nodes, edges, filters]);
  const nodeById = useMemo(() => new Map(nodes.map(node => [node.id, node])), [nodes]);
  const selected = visible.nodes.find(node => node.id === selectedId);
  const connections = visible.edges.filter(edge => edge.source === selected?.id || edge.target === selected?.id);
  const neighbors = new Set(connections.flatMap(edge => [edge.source, edge.target]));
  const selectedEdges = selected ? edges.filter(edge => edge.source === selected.id || edge.target === selected.id) : [];
  const invalidDates = !!(filters.from && filters.to && filters.from > filters.to);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setSize(current => current.x === width && current.y === height ? current : { x: width, y: height });
    });
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    particles.current = seedParticles(nodes, size, particles.current);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0, iteration = 0;
    const render = () => {
      const ticks = reducedMotion && !paused ? 120 : paused ? 0 : 2;
      for (let i = 0; i < ticks; i++) tickParticles(particles.current, edges, size, Math.max(.08, Math.pow(.96, iteration++)), drag.current?.node);
      setPositions(new Map(Array.from(particles.current, ([id, point]) => [id, { ...point }])));
      if (autoFit.current) setCamera(fitCamera([...particles.current.values()], size));
      if (!paused && !reducedMotion && (iteration < 140 || drag.current?.node)) frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => cancelAnimationFrame(frame);
  }, [nodes, edges, size, paused, revision]);

  const svgPoint = useCallback((x: number, y: number): Point => {
    const matrix = svgRef.current?.getScreenCTM();
    if (!matrix) return { x, y };
    const point = new DOMPoint(x, y).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); autoFit.current = false;
      const anchor = svgPoint(event.clientX, event.clientY);
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.y : 1);
      setCamera(current => zoomAt(current, Math.exp(-Math.max(-100, Math.min(100, delta)) * .003), anchor));
    };
    svg.addEventListener("wheel", wheel, { passive: false });
    return () => svg.removeEventListener("wheel", wheel);
  }, [svgPoint, size.y]);

  function fit() {
    autoFit.current = false;
    setCamera(fitCamera(visible.nodes.flatMap(node => positions.has(node.id) ? [positions.get(node.id)!] : []), size));
  }
  function zoom(factor: number) {
    autoFit.current = false;
    setCamera(current => zoomAt(current, factor, { x: size.x / 2, y: size.y / 2 }));
  }
  function pointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || drag.current) return;
    const point = svgPoint(event.clientX, event.clientY);
    const id = (event.target as Element).closest("[data-graph-node]")?.getAttribute("data-graph-node") ?? undefined;
    const particle = id ? particles.current.get(id) : undefined;
    autoFit.current = false; ignoreClick.current = false;
    drag.current = { pointer: event.pointerId, start: point, pan: camera.pan, node: id, moved: false,
      offset: { x: (point.x - camera.pan.x) / camera.zoom - (particle?.x ?? 0), y: (point.y - camera.pan.y) / camera.zoom - (particle?.y ?? 0) } };
    event.currentTarget.setPointerCapture(event.pointerId);
    if (id) setRevision(current => current + 1);
  }
  function pointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    const point = svgPoint(event.clientX, event.clientY);
    if (Math.hypot(point.x - current.start.x, point.y - current.start.y) > 3) current.moved = true;
    if (current.node) {
      const particle = particles.current.get(current.node);
      if (!particle) return;
      particle.x = (point.x - camera.pan.x) / camera.zoom - current.offset.x;
      particle.y = (point.y - camera.pan.y) / camera.zoom - current.offset.y;
      particle.vx = 0; particle.vy = 0;
      setPositions(new Map(Array.from(particles.current, ([id, p]) => [id, { ...p }])));
    } else setCamera(value => ({ ...value, pan: { x: current.pan.x + point.x - current.start.x, y: current.pan.y + point.y - current.start.y } }));
  }
  function pointerEnd(event: React.PointerEvent<SVGSVGElement>) {
    if (drag.current?.pointer !== event.pointerId) return;
    const current = drag.current;
    ignoreClick.current = current.moved;
    // Capture retargets click to the SVG, so handle pointer selection here.
    if (!current.moved && current.node && event.type !== "pointercancel") setSelectedId(value => value === current.node ? null : current.node!);
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  function exportGraph() {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ ...visible, filters }, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "terramind-graph.json"; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className={styles.container} aria-label="Knowledge graph">
    <header className={styles.header}>
      <div className={styles.headingBlock}><div className={styles.eyebrow}><span className={styles.liveDot} /> FIELD INTELLIGENCE</div><h1 className={styles.title}>Knowledge graph</h1><p className={styles.subtitle}>Drag nodes to explore connections. Select an entity to inspect its records. Saved documents show processing status; only extracted evidence represents agronomic relationships.</p></div>
      <div className={styles.summary} aria-label="Graph summary"><div className={styles.stat}><strong>{nodes.length}</strong><span>entities</span></div><span className={styles.statDivider} /><div className={styles.stat}><strong>{edges.length}</strong><span>relationships</span></div></div>
    </header>
    <div className={styles.workspace}>
      <div className={styles.toolbar}>
        <label className={styles.searchBox}><Search size={16} aria-hidden="true" /><input value={filters.query} onChange={event => setFilters(value => ({ ...value, query: event.target.value }))} placeholder="Find an entity…" aria-label="Search entities" />{filters.query && <button className={styles.clearSearch} onClick={() => setFilters(value => ({ ...value, query: "" }))} aria-label="Clear search">×</button>}</label>
        <label className={styles.filterLabel}>Type<select value={filters.type} onChange={event => setFilters(value => ({ ...value, type: event.target.value }))} aria-label="Filter by entity type"><option value="all">All entities</option>{[...new Set(nodes.map(node => node.type))].sort().map(type => <option key={type} value={type}>{humanize(type)}</option>)}</select></label>
        <span className={styles.resultCount} role="status">{visible.nodes.length} of {nodes.length} entities · {visible.edges.length} links shown</span>
        <div className={styles.controlGroup} aria-label="Graph controls">
          <button className={styles.controlBtn} onClick={() => zoom(1 / 1.2)} aria-label="Zoom out"><ZoomOut size={16} /></button><span className={styles.zoomValue}>{Math.round(camera.zoom * 100)}%</span><button className={styles.controlBtn} onClick={() => zoom(1.2)} aria-label="Zoom in"><ZoomIn size={16} /></button>
          <button className={styles.controlBtn} onClick={fit} aria-label="Fit graph" title="Fit visible entities"><Focus size={16} /></button>
          <button className={styles.controlBtn} onClick={() => { autoFit.current = true; setFilters(emptyFilters); setSelectedId(null); setRevision(value => value + 1); }} aria-label="Reset graph view"><RotateCcw size={16} /></button>
          <button className={styles.controlBtn} onClick={exportGraph} aria-label="Export visible graph" title="Export visible graph"><Download size={16} /></button>
        </div>
      </div>
      <div className={styles.dateFilters}>
        <label>From<input type="date" aria-label="Graph start date" value={filters.from} max={filters.to || undefined} onChange={event => setFilters(value => ({ ...value, from: event.target.value }))} /></label>
        <label>To<input type="date" aria-label="Graph end date" value={filters.to} min={filters.from || undefined} onChange={event => setFilters(value => ({ ...value, to: event.target.value }))} /></label>
        <span>{invalidDates ? <span role="alert">Start date must be on or before end date.</span> : "Undated entities remain visible."}</span>
      </div>
      <div className={styles.canvas}>
        <div className={styles.canvasHint}>Drag nodes · drag background to pan · scroll to zoom</div>
        <svg ref={svgRef} className={styles.svg} viewBox={`0 0 ${size.x} ${size.y}`} role="group" aria-label={`Interactive knowledge graph with ${visible.nodes.length} entities and ${visible.edges.length} relationships`} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd} onPointerCancel={pointerEnd} onLostPointerCapture={() => { drag.current = null; }}>
          <defs><pattern id={`${graphId}-grid`} width="38" height="38" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="rgba(148,163,184,.17)" /></pattern>{Object.entries(EDGE_COLORS).map(([type, color]) => <marker key={type} id={`${graphId}-${type}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" fill={color} /></marker>)}</defs>
          <rect width={size.x} height={size.y} fill={`url(#${graphId}-grid)`} />
          <g transform={`translate(${camera.pan.x} ${camera.pan.y}) scale(${camera.zoom})`}>
            {visible.edges.map(edge => {
              const a = positions.get(edge.source), b = positions.get(edge.target);
              if (!a || !b) return null;
              const distance = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y));
              const shorten = Math.min(radius(nodeById.get(edge.target)) + 6, distance / 2);
              const target = { x: b.x - (b.x - a.x) / distance * shorten, y: b.y - (b.y - a.y) / distance * shorten };
              const active = selected ? edge.source === selected.id || edge.target === selected.id : edge.source === hoveredId || edge.target === hoveredId;
              const color = EDGE_COLORS[edge.type] ?? "#94a3b8";
              return <g key={edge.id} className={styles.edge} opacity={selected && !active ? .13 : active ? 1 : .5}><line x1={a.x} y1={a.y} x2={target.x} y2={target.y} stroke={color} strokeWidth={active ? 2.6 : 1.5} strokeDasharray={edge.confirmed ? undefined : "6 6"} markerEnd={`url(#${graphId}-${edge.type})`} /><title>{humanize(edge.type)}{edge.source_document_id ? ` · source ${edge.source_document_id}` : ""}</title>{labels && (active || visible.edges.length < 12) && <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 8} textAnchor="middle" fill={color} fontSize="9" paintOrder="stroke" stroke="#101821" strokeWidth="4">{humanize(edge.type)}</text>}</g>;
            })}
            {visible.nodes.map(node => {
              const point = positions.get(node.id); if (!point) return null;
              const color = NODE_COLORS[node.type] ?? "#94a3b8", isSelected = selected?.id === node.id, r = radius(node);
              return <g key={node.id} data-graph-node={node.id} transform={`translate(${point.x} ${point.y})`} className={styles.node} opacity={selected && !isSelected && !neighbors.has(node.id) ? .25 : 1} role="button" tabIndex={0} aria-label={`${node.label}, ${node.type}`} aria-pressed={isSelected}
                onClick={event => { if (event.detail === 0 && !ignoreClick.current) setSelectedId(isSelected ? null : node.id); }}
                onKeyDown={event => {
                  if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(isSelected ? null : node.id); }
                  if (event.key === "Escape") setSelectedId(null);
                  const delta: Record<string, Point> = { ArrowLeft: { x: -15, y: 0 }, ArrowRight: { x: 15, y: 0 }, ArrowUp: { x: 0, y: -15 }, ArrowDown: { x: 0, y: 15 } };
                  const p = particles.current.get(node.id);
                  if (p && delta[event.key]) { event.preventDefault(); autoFit.current = false; p.x += delta[event.key].x; p.y += delta[event.key].y; setPositions(new Map(Array.from(particles.current, ([id, item]) => [id, { ...item }]))); }
                }} onMouseEnter={() => setHoveredId(node.id)} onMouseLeave={() => setHoveredId(null)}>
                <title>{node.label} — {humanize(node.type)}. Arrow keys move this node.</title><circle r={r + 6} fill="none" stroke={color} opacity={isSelected ? .7 : .15} /><circle r={r} fill={node.type === "Field" ? "#173426" : "#111b25"} stroke={color} strokeWidth={isSelected ? 3 : 1.5} />
                <text y="3" textAnchor="middle" fill="#edf5f3" fontSize="9" fontWeight="700" pointerEvents="none">{node.type === "Document" ? "DOC" : readable(node.label, 11)}</text><text y={r + 18} textAnchor="middle" fill="#b4c4cd" fontSize="10" pointerEvents="none">{readable(node.label)}</text>
              </g>;
            })}
          </g>
        </svg>
        {visible.nodes.length === 0 && <div className={styles.emptyOverlay} role="status"><h2>{nodes.length ? "No entities match these filters" : "Your field graph is ready to grow"}</h2><p>{nodes.length ? "Adjust the search, type, or date range." : "Add a field record to see its connections here."}</p></div>}
        <div className={styles.canvasFooter}>
          <button className={`${styles.toggle} ${filters.confirmed ? styles.toggleActive : ""}`} onClick={() => setFilters(value => ({ ...value, confirmed: !value.confirmed }))} aria-pressed={filters.confirmed}>Confirmed links only</button>
          <button className={styles.toggle} onClick={() => setLabels(value => !value)} aria-pressed={labels}>Relationship labels</button>
          <button className={styles.toggle} onClick={() => setPaused(value => !value)} aria-pressed={paused}>{paused ? <Play size={12} /> : <Pause size={12} />}{paused ? "Resume layout" : "Pause layout"}</button>
          <div className={styles.legendInline}><span><i className={styles.confirmedLine} />Recorded / confirmed</span><span><i className={styles.uncertainLine} />Unconfirmed</span></div>
        </div>
      </div>
    </div>
    {selected && <aside className={styles.inspector} aria-label="Selected entity details"><div className={styles.inspectorHeader}><div className={styles.inspectorHeading}><span className={styles.inspectorType} style={{ color: NODE_COLORS[selected.type] }}>{humanize(selected.type)}</span><h2 className={styles.inspectorLabel}>{selected.label}</h2></div><button className={styles.closeInspector} onClick={() => setSelectedId(null)} aria-label="Close entity details">×</button></div>
      {selected.date && <div className={styles.inspectorDate}>RECORDED <strong>{selected.date}</strong></div>}
      <div className={styles.inspectorProps}>{Object.entries(selected.properties).map(([key, value]) => <div key={key} className={styles.propRow}><span>{humanize(key)}</span><strong>{String(value)}</strong></div>)}</div>
      <div className={styles.inspectorEdges}><h3>Connected evidence <span>{selectedEdges.length}</span></h3>{selectedEdges.length === 0 && <p className={styles.noConnections}>No relationships recorded for this entity yet.</p>}{selectedEdges.map(edge => {
        const other = nodeById.get(edge.source === selected.id ? edge.target : edge.source);
        return <button key={edge.id} className={styles.edgeRow} onClick={() => { setFilters(emptyFilters); setSelectedId(other?.id ?? null); }}><span className={styles.edgeContent}><strong>{other?.label ?? "Unknown entity"}</strong><small>{humanize(edge.type)}{edge.source_document_id ? ` · source: ${edge.source_document_id}` : ""}</small></span><span className={`${styles.statusBadge} ${edge.confirmed ? styles.confirmed : styles.review}`}>{edge.confirmed ? "Recorded" : "Unconfirmed"}</span></button>;
      })}</div>
    </aside>}
  </section>;
}
