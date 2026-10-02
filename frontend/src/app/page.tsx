"use client";
import React, { useEffect, useMemo, useState } from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import DashboardView from "@/components/dashboard/DashboardView";
import QueryView from "@/components/query/QueryView";
import TimelineView from "@/components/timeline/TimelineView";
import GraphView from "@/components/graph/GraphView";
import CaptureView from "@/components/onboarding/CaptureView";
import AuthScreen from "@/components/auth/AuthScreen";
import LiveWorkspace from "@/components/dashboard/LiveWorkspace";
import {
  mockFarm, mockDocuments, mockStats, mockTimeline,
  mockQueue, mockGraphNodes, mockGraphEdges, suggestedQueries
} from "@/data/mock";
import type { DashboardStats, Document, GraphEdge, GraphNode, IngestionQueueItem, Plot, TimelineEvent, User } from "@/types";
import styles from "./page.module.css";

type Section = "dashboard" | "query" | "timeline" | "graph" | "capture";
type DemoData = { documents: Document[]; timeline: TimelineEvent[]; queue: IngestionQueueItem[]; totalQueries: number };
const STORAGE_KEY = "aegis-demo-data-v1";
const defaultData: DemoData = { documents: mockDocuments, timeline: mockTimeline, queue: mockQueue, totalQueries: mockStats.total_queries };

function readDemoData(): DemoData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultData;
    const data = JSON.parse(raw) as Partial<DemoData>;
    return {
      documents: Array.isArray(data.documents) ? data.documents : mockDocuments,
      timeline: Array.isArray(data.timeline) ? data.timeline : mockTimeline,
      queue: Array.isArray(data.queue) ? data.queue : mockQueue,
      totalQueries: typeof data.totalQueries === "number" ? data.totalQueries : mockStats.total_queries,
    };
  } catch { return defaultData; }
}

function DemoWorkspace({ onExitDemo }: { onExitDemo: () => void }) {
  const [section, setSection] = useState<Section>("dashboard");
  const [activePlot, setActivePlot] = useState<Plot>(mockFarm.plots[1]);
  const [pendingQuery, setPendingQuery] = useState<string | undefined>();
  const [data, setData] = useState<DemoData>(defaultData);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => { setData(readDemoData()); setHydrated(true); }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (hydrated) localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }, [data, hydrated]);

  function navigateToQuery(q: string) { setPendingQuery(q); setSection("query"); }
  function handleSectionChange(s: string) {
    setSection(s as Section);
    if (s !== "query") setPendingQuery(undefined);
  }

  const plotDocs = useMemo(() => data.documents.filter(d => d.plot_id === activePlot.id), [data.documents, activePlot.id]);
  const plotTimeline = useMemo(() => {
    const events = data.timeline.filter(event => event.plot_id === activePlot.id);
    const linkedDocuments = new Set(events.map(event => event.document_id).filter(Boolean));
    const documentEvents: TimelineEvent[] = data.documents
      .filter(document => document.plot_id === activePlot.id && !linkedDocuments.has(document.id))
      .map(document => ({ id: `document-event-${document.id}`, date: document.date_of_event ?? document.uploaded_at.slice(0, 10), title: "Document in sample records", category: "practice", description: `${document.label} is listed in the local demo records.`, document_id: document.id, plot_id: activePlot.id, confidence: document.source_confidence }));
    return [...events, ...documentEvents];
  }, [data.timeline, data.documents, activePlot.id]);
  const plotQueue = useMemo(() => data.queue.filter(item => {
    const document = data.documents.find(doc => doc.id === item.document_id);
    return !document || document.plot_id === activePlot.id;
  }), [data.queue, data.documents, activePlot.id]);
  const stats: DashboardStats = {
    ...mockStats,
    total_documents: plotDocs.length,
    total_queries: data.totalQueries,
    pending_review: plotQueue.filter(item => item.status === "pending").length,
    avg_confidence: plotDocs.length ? plotDocs.reduce((sum, doc) => sum + (doc.source_confidence ?? 0), 0) / plotDocs.length : 0,
    graph_nodes: activePlot.id === "plot-B" ? mockGraphNodes.length : plotDocs.length + 1,
    graph_edges: activePlot.id === "plot-B" ? mockGraphEdges.length : plotDocs.length,
  };
  const graph = useMemo(() => {
    if (activePlot.id === "plot-B") {
      const represented = new Set(mockGraphEdges.map(edge => edge.source_document_id).filter(Boolean));
      const additionalDocuments = plotDocs.filter(document => !represented.has(document.id));
      const extraNodes: GraphNode[] = additionalDocuments.map((document, index) => ({
        id: `document-${document.id}`, type: "Practice", label: document.label,
        date: document.date_of_event ?? document.uploaded_at.slice(0, 10), properties: { source: document.source_type, status: document.ingest_status },
        x: 200 + (index % 2) * 400, y: 110 + Math.floor(index / 2) * 110,
      }));
      const extraEdges: GraphEdge[] = additionalDocuments.map(document => ({
        id: `edge-${document.id}`, source: `document-${document.id}`, target: "n-field-B", type: "APPLIED_TO",
        date: document.date_of_event, source_document_id: document.id, confirmed: document.ingest_status === "ready",
      }));
      return { nodes: [...mockGraphNodes, ...extraNodes], edges: [...mockGraphEdges, ...extraEdges] };
    }
    const fieldNode: GraphNode = {
      id: `field-${activePlot.id}`, type: "Field", label: activePlot.name.split(" — ")[0],
      properties: { crop_type: activePlot.crop_type, size_ha: activePlot.size_ha },
    };
    const nodes: GraphNode[] = [fieldNode, ...plotDocs.map((doc, index) => ({
      id: `document-${doc.id}`, type: "Practice" as const, label: doc.label,
      date: doc.date_of_event ?? doc.uploaded_at.slice(0, 10), properties: { source: doc.source_type, status: doc.ingest_status },
      x: 220 + (index % 2) * 360, y: 150 + index * 100,
    }))];
    const edges: GraphEdge[] = plotDocs.map(doc => ({
      id: `edge-${doc.id}`, source: `document-${doc.id}`, target: fieldNode.id,
      type: "APPLIED_TO", date: doc.date_of_event, source_document_id: doc.id, confirmed: doc.ingest_status === "ready",
    }));
    return { nodes, edges };
  }, [activePlot, plotDocs]);

  return (
    <div className={styles.layout}>
      <Sidebar farm={mockFarm} activePlot={activePlot}
        onPlotChange={p => { setActivePlot(p); setSection("dashboard"); }}
        activeSection={section} onSectionChange={handleSectionChange}
        pendingCount={plotQueue.filter(item => item.status === "pending").length}
        onResetDemo={() => { setData(defaultData); localStorage.removeItem(STORAGE_KEY); }} />
      <main className={styles.main}>
        <p role="status" style={{ padding: "10px 24px", margin: 0, background: "#173322", color: "#d1fae5", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <span>Local demo preview: sample records and browser-only changes. No files leave this device.</span>
          <button className="btn btn-secondary" onClick={onExitDemo}>Sign in</button>
        </p>
        {section === "dashboard" && <DashboardView stats={stats} plot={activePlot} documents={plotDocs} onAskQuery={navigateToQuery} demoMode />}
        {section === "query" && <QueryView key={`${activePlot.id}:${pendingQuery ?? ""}`} initialQuery={pendingQuery} plotId={activePlot.id} plotName={activePlot.name} userRole="farmer" demoMode documents={plotDocs} suggestedQueries={suggestedQueries} onQueryComplete={() => setData(current => ({ ...current, totalQueries: current.totalQueries + 1 }))} />}
        {section === "timeline" && <TimelineView events={plotTimeline} plot={activePlot} />}
        {section === "graph" && <GraphView key={activePlot.id} nodes={graph.nodes} edges={graph.edges} />}
        {section === "capture" && <CaptureView plot={activePlot} queue={plotQueue} documents={plotDocs}
          onQueueChange={queue => setData(current => ({ ...current, queue: current.queue.map(item => queue.find(next => next.id === item.id) ?? item).concat(queue.filter(next => !current.queue.some(item => item.id === next.id))) }))}
          onDocumentAdd={document => setData(current => ({ ...current, documents: [document, ...current.documents] }))}
          onDocumentUpdate={document => setData(current => ({ ...current, documents: current.documents.map(item => item.id === document.id ? document : item) }))}
          onTimelineAdd={event => setData(current => ({ ...current, timeline: [event, ...current.timeline] }))} />}
      </main>
    </div>
  );
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [demoPreview, setDemoPreview] = useState(false);

  useEffect(() => {
    fetch("/api/auth/session", { cache: "no-store" })
      .then(response => response.json())
      .then(data => setUser(data.user ?? null))
      .catch(() => setUser(null))
      .finally(() => setCheckingSession(false));
  }, []);

  if (demoPreview && !user) return <DemoWorkspace onExitDemo={() => setDemoPreview(false)} />;
  if (checkingSession) return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "var(--bg-deep)", color: "var(--text-primary)" }}>Checking your session…</main>;
  if (!user) return <AuthScreen onAuthenticated={setUser} onPreviewDemo={() => setDemoPreview(true)} />;
  return <LiveWorkspace user={user} onLogout={async () => { await fetch("/api/auth/session", { method: "DELETE" }); setUser(null); setDemoPreview(false); }} />;
}
