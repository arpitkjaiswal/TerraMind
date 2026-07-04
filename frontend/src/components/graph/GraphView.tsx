"use client";
import React, { useRef, useState } from "react";
import type { GraphNode, GraphEdge } from "@/types";
import styles from "./GraphView.module.css";
import { ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  Field: "#22c55e",
  ChemicalProduct: "#f59e0b",
  WeatherEvent: "#38bdf8",
  CropVariant: "#4ade80",
  YieldMeasurement: "#f87171",
  Practice: "#fb923c",
};

const LAYOUT_POSITIONS: Record<string, { x: number; y: number }> = {
  "n-field-B":   { x: 430, y: 255 },
  "n-chem-001":  { x: 240, y: 140 },
  "n-prac-001":  { x: 640, y: 140 },
  "n-wx-001":    { x: 240, y: 380 },
  "n-yield-001": { x: 640, y: 380 },
  "n-crop-001":  { x: 430, y: 60 },
};

const EDGE_COLOR: Record<string, string> = {
  APPLIED_TO: "#22c55e",
  OCCURRED_DURING: "#38bdf8",
  CORRELATED_WITH: "#f59e0b",
  CONFIRMED_CAUSE: "#f87171",
  PRECEDED: "#a78bfa",
};

export default function GraphView({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState<string | null>(null);

  const nodePos = (id: string) => LAYOUT_POSITIONS[id] ?? { x: 400, y: 250 };

  function onMouseDown(e: React.MouseEvent) {
    setDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }
  function onMouseUp() { setDragging(false); }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Knowledge Graph</h1>
          <p className={styles.subtitle}>Entities and time-stamped relationships extracted by Cognee. Click a node to inspect.</p>
        </div>
        <div className={styles.controls}>
          <button className={styles.controlBtn} onClick={() => setZoom(z => Math.min(z + 0.2, 3))}><ZoomIn size={15} /></button>
          <button className={styles.controlBtn} onClick={() => setZoom(z => Math.max(z - 0.2, 0.4))}><ZoomOut size={15} /></button>
          <button className={styles.controlBtn} onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}><RotateCcw size={15} /></button>
        </div>
      </div>

      <div className={styles.canvas}>
        <svg ref={svgRef} className={styles.svg} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
          <defs>
            {Object.entries(EDGE_COLOR).map(([type, color]) => (
              <marker key={type} id={`arrow-${type}`} markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill={color} opacity="0.8" />
              </marker>
            ))}
          </defs>
          <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
            {edges.map(edge => {
              const sp = nodePos(edge.source);
              const tp = nodePos(edge.target);
              const color = EDGE_COLOR[edge.type] ?? "#888";
              const highlighted = hovered === edge.source || hovered === edge.target;
              return (
                <g key={edge.id}>
                  <line x1={sp.x} y1={sp.y} x2={tp.x} y2={tp.y}
                    stroke={color} strokeWidth={highlighted ? 2.5 : 1.5}
                    strokeOpacity={highlighted ? 0.9 : 0.35}
                    strokeDasharray={edge.confirmed ? undefined : "5,4"}
                    markerEnd={`url(#arrow-${edge.type})`} />
                  <text x={(sp.x+tp.x)/2} y={(sp.y+tp.y)/2 - 5} textAnchor="middle"
                    fontSize="9" fill={color} opacity={highlighted ? 0.9 : 0.4} fontFamily="JetBrains Mono">
                    {edge.type.replace(/_/g," ")}
                  </text>
                </g>
              );
            })}
            {nodes.map(node => {
              const pos = nodePos(node.id);
              const color = NODE_COLORS[node.type] ?? "#888";
              const isSelected = selected?.id === node.id;
              const isHov = hovered === node.id;
              const r = node.type === "Field" ? 38 : 28;
              const words = node.label.split(" ").slice(0, 3);
              return (
                <g key={node.id} transform={`translate(${pos.x},${pos.y})`}
                  onClick={() => setSelected(isSelected ? null : node)}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: "pointer" }}>
                  {(isSelected || isHov) && <circle r={r+8} fill="none" stroke={color} strokeWidth="1.5" opacity="0.3" />}
                  <circle r={r} fill={`${color}20`} stroke={color} strokeWidth={isSelected ? 2.5 : 1.5} />
                  {words.map((w, i) => (
                    <text key={i} x="0" y={words.length > 1 ? (i - (words.length-1)/2) * 13 : 0}
                      textAnchor="middle" dominantBaseline="middle"
                      fontSize={node.type==="Field"?"11":"9"} fontWeight="600" fill={color} fontFamily="Inter"
                      style={{ userSelect:"none", pointerEvents:"none" }}>
                      {w}
                    </text>
                  ))}
                  <text y={r+14} textAnchor="middle" fontSize="9" fill="var(--text-muted)" fontFamily="JetBrains Mono"
                    style={{ userSelect:"none", pointerEvents:"none" }}>
                    {node.type}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        <div className={styles.legend}>
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className={styles.legendItem}>
              <div className={styles.legendDot} style={{ background: color }} /><span>{type}</span>
            </div>
          ))}
          <div className={styles.legendDivider} />
          <div className={styles.legendItem}><div className={styles.legendLine} style={{ background: "var(--text-muted)" }} /><span>Confirmed</span></div>
          <div className={styles.legendItem}><div className={styles.legendDash} /><span>Correlated</span></div>
        </div>
      </div>

      {selected && (
        <div className={`${styles.inspector} animate-slide-left`}>
          <div className={styles.inspectorHeader}>
            <div className={styles.inspectorDot} style={{ background: `${NODE_COLORS[selected.type]}20`, border: `2px solid ${NODE_COLORS[selected.type]}` }} />
            <div>
              <div className={styles.inspectorType} style={{ color: NODE_COLORS[selected.type] }}>{selected.type}</div>
              <div className={styles.inspectorLabel}>{selected.label}</div>
            </div>
          </div>
          {selected.date && <div className={styles.inspectorDate}>📅 {selected.date}</div>}
          <div className={styles.inspectorProps}>
            {Object.entries(selected.properties).map(([k, v]) => (
              <div key={k} className={styles.propRow}>
                <span className={styles.propKey}>{k}</span>
                <span className={styles.propVal}>{String(v)}</span>
              </div>
            ))}
          </div>
          <div className={styles.inspectorEdges}>
            <div className={styles.inspectorEdgeTitle}>Connections</div>
            {edges.filter(e => e.source===selected.id||e.target===selected.id).map(e => {
              const other = nodes.find(n => n.id===(e.source===selected.id?e.target:e.source));
              return (
                <div key={e.id} className={styles.edgeRow}>
                  <span className={styles.edgeType} style={{ color: EDGE_COLOR[e.type]??"#888" }}>{e.type.replace(/_/g," ")}</span>
                  <span className={styles.edgeTarget}>{other?.label??"?"}</span>
                  {!e.confirmed && <span className={styles.edgeUnconfirmed}>unconfirmed</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
