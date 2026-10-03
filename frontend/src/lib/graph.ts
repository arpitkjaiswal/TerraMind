import type { GraphNode, GraphEdge } from "../types/index";

export type Point = { x: number; y: number };
export type Camera = { pan: Point; zoom: number };
export type Particle = Point & { id: string; vx: number; vy: number };
export type GraphFilters = { query: string; type: string; confirmed: boolean; from: string; to: string };
export const emptyFilters: GraphFilters = { query: "", type: "all", confirmed: false, from: "", to: "" };

export function filterGraph(nodes: GraphNode[], edges: GraphEdge[], filters: GraphFilters) {
  const query = filters.query.trim().toLowerCase();
  const inRange = (date?: string) => !date || ((!filters.from || date >= filters.from) && (!filters.to || date <= filters.to));
  const invalidRange = !!(filters.from && filters.to && filters.from > filters.to);
  const filteredNodes = invalidRange ? [] : nodes.filter(node =>
    (filters.type === "all" || node.type === filters.type) && inRange(node.date) &&
    (!query || `${node.label} ${node.type} ${Object.values(node.properties).join(" ")}`.toLowerCase().includes(query)));
  const ids = new Set(filteredNodes.map(node => node.id));
  const filteredEdges = edges.filter(edge => ids.has(edge.source) && ids.has(edge.target) &&
    inRange(edge.date) && (!filters.confirmed || edge.confirmed));
  return { nodes: filteredNodes, edges: filteredEdges };
}

/** Retain existing positions when records arrive; spread new nodes deterministically. */
export function seedParticles(nodes: GraphNode[], size: Point, previous = new Map<string, Particle>()) {
  return new Map(nodes.map((node, index) => {
    const old = previous.get(node.id);
    const angle = index * Math.PI * (3 - Math.sqrt(5));
    const radius = Math.min(size.x, size.y) * .36 * Math.sqrt((index + 1) / Math.max(nodes.length, 1));
    return [node.id, old ? { ...old } : {
      id: node.id, x: size.x / 2 + Math.cos(angle) * radius, y: size.y / 2 + Math.sin(angle) * radius, vx: 0, vy: 0,
    }];
  }));
}

/** Spatial buckets bound repulsion work for larger document collections. */
export function tickParticles(particles: Map<string, Particle>, edges: GraphEdge[], size: Point, alpha: number, pinned?: string) {
  const buckets = new Map<string, Particle[]>();
  const cell = 120;
  for (const p of particles.values()) {
    const key = `${Math.floor(p.x / cell)},${Math.floor(p.y / cell)}`;
    const bucket = buckets.get(key) ?? [];
    bucket.push(p); buckets.set(key, bucket);
  }
  for (const p of particles.values()) {
    const bx = Math.floor(p.x / cell), by = Math.floor(p.y / cell);
    for (let x = bx - 1; x <= bx + 1; x++) for (let y = by - 1; y <= by + 1; y++) {
      for (const q of buckets.get(`${x},${y}`) ?? []) {
        if (p === q) continue;
        const dx = p.x - q.x || (p.id < q.id ? -.1 : .1), dy = p.y - q.y || .1;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const strength = Math.min(5, 500 / (distance * distance) + Math.max(0, 84 - distance) * .07) * alpha;
        p.vx += dx / distance * strength; p.vy += dy / distance * strength;
      }
    }
  }
  for (const edge of edges) {
    const a = particles.get(edge.source), b = particles.get(edge.target);
    if (!a || !b) continue;
    const dx = b.x - a.x, dy = b.y - a.y, distance = Math.max(1, Math.hypot(dx, dy));
    const force = (distance - 155) * .009 * alpha;
    a.vx += dx / distance * force; a.vy += dy / distance * force;
    b.vx -= dx / distance * force; b.vy -= dy / distance * force;
  }
  for (const p of particles.values()) {
    if (p.id === pinned) { p.vx = 0; p.vy = 0; continue; }
    p.vx = (p.vx + (size.x / 2 - p.x) * .001 * alpha) * .72;
    p.vy = (p.vy + (size.y / 2 - p.y) * .001 * alpha) * .72;
    p.x += Math.max(-12, Math.min(12, p.vx)); p.y += Math.max(-12, Math.min(12, p.vy));
  }
}

export function fitCamera(points: Point[], size: Point): Camera {
  if (!points.length) return { pan: { x: 0, y: 0 }, zoom: 1 };
  const xs = points.map(point => point.x), ys = points.map(point => point.y);
  const left = Math.min(...xs) - 65, right = Math.max(...xs) + 65;
  const top = Math.min(...ys) - 65, bottom = Math.max(...ys) + 65;
  const zoom = Math.min(1.5, (size.x - 32) / (right - left), (size.y - 64) / (bottom - top));
  return { zoom, pan: { x: size.x / 2 - (left + right) / 2 * zoom, y: size.y / 2 - (top + bottom) / 2 * zoom } };
}

export function zoomAt(camera: Camera, factor: number, anchor: Point): Camera {
  const zoom = Math.max(.08, Math.min(4, camera.zoom * factor));
  const ratio = zoom / camera.zoom;
  return { zoom, pan: { x: anchor.x - (anchor.x - camera.pan.x) * ratio, y: anchor.y - (anchor.y - camera.pan.y) * ratio } };
}
