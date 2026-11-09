"use client";
import React, { useEffect, useMemo, useState } from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import DashboardView from "@/components/dashboard/DashboardView";
import QueryView from "@/components/query/QueryView";
import TimelineView from "@/components/timeline/TimelineView";
import GraphView from "@/components/graph/GraphView";
import CaptureView from "@/components/onboarding/CaptureView";
import {
  mockFarm, mockDocuments, mockStats, mockTimeline,
  mockQueue, mockGraphNodes, mockGraphEdges, suggestedQueries
} from "@/data/mock";
import type { DashboardStats, Plot, TimelineEvent } from "@/types";
import styles from "./page.module.css";
import { sampleDemoDocuments, sampleDocuments } from "@/data/sample-documents";
import { buildDemoGraph } from "@/lib/demo-graph";
import { restoreWorkspace, type WorkspaceData } from "@/lib/workspace-storage";

type Section = "dashboard" | "query" | "timeline" | "graph" | "capture";

const STORAGE_KEY = "aegis-demo-data-v1";
const defaultData: WorkspaceData = { documents: [...mockDocuments, ...sampleDemoDocuments], timeline: mockTimeline, queue: mockQueue, totalQueries: mockStats.total_queries };

function readDemoData(): WorkspaceData {
  try { return restoreWorkspace(localStorage.getItem(STORAGE_KEY), defaultData, sampleDemoDocuments); }
  catch { return defaultData; }
}

function DemoWorkspace() {
  const [section, setSection] = useState<Section>("dashboard");
  const [activePlot, setActivePlot] = useState<Plot>(mockFarm.plots[1]);
  const [pendingQuery, setPendingQuery] = useState<string | undefined>();
  const [data, setData] = useState<WorkspaceData>(defaultData);
  const [hydrated, setHydrated] = useState(false);
  const [storageError, setStorageError] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => { setData(readDemoData()); setHydrated(true); }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!hydrated) return;
    const timer = window.setTimeout(() => {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); setStorageError(false); }
      catch { setStorageError(true); }
    }, 0);
    return () => window.clearTimeout(timer);
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
  const graph = useMemo(() => buildDemoGraph(activePlot, plotDocs, sampleDocuments,
    activePlot.id === "plot-B" ? { nodes: mockGraphNodes, edges: mockGraphEdges } : undefined), [activePlot, plotDocs]);
  const stats: DashboardStats = {
    ...mockStats,
    total_documents: plotDocs.length,
    total_queries: data.totalQueries,
    pending_review: plotQueue.filter(item => item.status === "pending").length,
    avg_confidence: plotDocs.length ? plotDocs.reduce((sum, doc) => sum + (doc.source_confidence ?? 0), 0) / plotDocs.length : 0,
    graph_nodes: graph.nodes.length,
    graph_edges: graph.edges.length,
  };


  return (
    <div className={styles.layout}>
      <Sidebar farm={mockFarm} activePlot={activePlot}
        onPlotChange={p => { setActivePlot(p); setSection("dashboard"); }}
        activeSection={section} onSectionChange={handleSectionChange}
        pendingCount={plotQueue.filter(item => item.status === "pending").length}
        onResetDemo={() => { setData(defaultData); try { localStorage.removeItem(STORAGE_KEY); } catch { /* Storage is optional in demo mode. */ } }} />
      <main className={styles.main}>
        <p role="status" style={{ padding: "10px 24px", margin: 0, background: "#173322", color: "#d1fae5", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <span>Interactive sandbox · No account needed · Your changes stay in this browser.</span>
        </p>
        {storageError && <p role="alert" style={{ padding: "12px 24px" }}>Browser storage is unavailable or full. Changes work in this session but may be lost when you reload.</p>}
        {section === "dashboard" && <DashboardView stats={stats} plot={activePlot} documents={plotDocs} onAskQuery={navigateToQuery} demoMode />}
        {section === "query" && <QueryView key={`${activePlot.id}:${pendingQuery ?? ""}`} initialQuery={pendingQuery} plotId={activePlot.id} plotName={activePlot.name} userRole="farmer" demoMode documents={plotDocs} suggestedQueries={suggestedQueries} onQueryComplete={() => setData(current => ({ ...current, totalQueries: current.totalQueries + 1 }))} />}
        {section === "timeline" && <TimelineView events={plotTimeline} plot={activePlot} demoMode />}
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
  return <DemoWorkspace />;
}
