"use client";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import type { DashboardStats, Document, Farm, GraphEdge, GraphNode, IngestionQueueItem, Plot, TimelineEvent, User } from "@/types";
import { backendFetch } from "@/lib/api";
import Sidebar from "@/components/dashboard/Sidebar";
import DashboardView from "@/components/dashboard/DashboardView";
import QueryView from "@/components/query/QueryView";
import TimelineView from "@/components/timeline/TimelineView";
import GraphView from "@/components/graph/GraphView";
import LiveCaptureView from "@/components/onboarding/LiveCaptureView";
import styles from "@/app/page.module.css";

type Section = "dashboard" | "query" | "timeline" | "graph" | "capture";
interface Props { user: User; onLogout: () => void; }
interface FarmRecord extends Omit<Farm, "plots"> { plots?: Plot[]; }
interface ReviewRecord { document_id: string; label: string; source_type: IngestionQueueItem["source_type"]; source_confidence: number; extracted_text: string; uploaded_at: string; }
interface QueryHistory { query_id: string; query_text: string; }
interface GraphResponse { nodes: GraphNode[]; edges: Omit<GraphEdge, "id">[]; }

export default function LiveWorkspace({ user, onLogout }: Props) {
  const [farm, setFarm] = useState<Farm | null>(null);
  const [plots, setPlots] = useState<Plot[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [queue, setQueue] = useState<IngestionQueueItem[]>([]);
  const [activePlotId, setActivePlotId] = useState("");
  const [section, setSection] = useState<Section>("dashboard");
  const [pendingQuery, setPendingQuery] = useState<string | undefined>();
  const [queryCount, setQueryCount] = useState(0);
  const [graphResponse, setGraphResponse] = useState<GraphResponse>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreatePlot, setShowCreatePlot] = useState(false);

  const refreshWorkspace = useCallback(async () => {
    const [farmRecord, plotRecords, documentRecords, queueRecords] = await Promise.all([
      backendFetch<FarmRecord>("farms/me"),
      backendFetch<Plot[]>("plots/"),
      backendFetch<Document[]>("documents/"),
      backendFetch<ReviewRecord[]>("documents/review-queue"),
    ]);
    setFarm({ ...farmRecord, plots: plotRecords });
    setPlots(plotRecords);
    setDocuments(documentRecords);
    setQueue(queueRecords.map(item => ({ id: item.document_id, document_id: item.document_id, label: item.label, source_type: item.source_type, confidence: item.source_confidence, extracted_text: item.extracted_text, uploaded_at: item.uploaded_at, status: "pending" })));
    setActivePlotId(current => plotRecords.some(plot => plot.id === current) ? current : plotRecords[0]?.id ?? "");
  }, []);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      refreshWorkspace().catch(cause => { if (mounted) setError(cause instanceof Error ? cause.message : "Could not load your farm data."); }).finally(() => { if (mounted) setLoading(false); });
    }, 0);
    return () => { mounted = false; window.clearTimeout(timer); };
  }, [refreshWorkspace]);

  const activePlot = plots.find(plot => plot.id === activePlotId) ?? null;
  const plotDocuments = useMemo(() => documents.filter(document => document.plot_id === activePlot?.id), [documents, activePlot?.id]);
  const plotQueue = useMemo(() => queue.filter(item => documents.find(document => document.id === item.document_id)?.plot_id === activePlot?.id), [queue, documents, activePlot?.id]);
  const timelineEvents = useMemo<TimelineEvent[]>(() => plotDocuments.map(document => {
    const label = document.label.toLowerCase();
    const category: TimelineEvent["category"] = label.includes("yield") ? "yield" : label.includes("weather") || label.includes("rain") || label.includes("drought") ? "weather" : label.includes("pesticide") || label.includes("chemical") || label.includes("fertilizer") ? "chemical" : label.includes("crop") ? "crop" : "practice";
    return { id: document.id, date: document.date_of_event ?? document.uploaded_at.slice(0, 10), title: document.label, category, description: `Ingestion status: ${document.ingest_status.replaceAll("_", " ")}.`, document_id: document.id, plot_id: document.plot_id, confidence: document.source_confidence };
  }), [plotDocuments]);

  useEffect(() => {
    if (!activePlot || (section !== "graph" && section !== "dashboard")) return;
    backendFetch<GraphResponse>(`plots/${encodeURIComponent(activePlot.id)}/graph`).then(setGraphResponse).catch(cause => setError(cause instanceof Error ? cause.message : "Could not load the field graph."));
  }, [activePlot, section]);
  useEffect(() => {
    if (!activePlot) return;
    backendFetch<QueryHistory[]>(`query/history?plot_id=${encodeURIComponent(activePlot.id)}&limit=100`).then(rows => setQueryCount(rows.length)).catch(() => setQueryCount(0));
  }, [activePlot]);

  const graph = useMemo(() => {
    const nodes = graphResponse.nodes.map((node, index) => {
      const angle = (index / Math.max(graphResponse.nodes.length, 1)) * Math.PI * 2;
      const radius = node.type === "Field" ? 0 : 155;
      return { ...node, x: node.type === "Field" ? 430 : 430 + Math.cos(angle) * radius, y: node.type === "Field" ? 250 : 250 + Math.sin(angle) * radius };
    });
    const edges: GraphEdge[] = graphResponse.edges.map((edge, index) => ({ ...edge, id: `live-edge-${index}-${edge.source}-${edge.target}` }));
    return { nodes, edges };
  }, [graphResponse]);
  const stats: DashboardStats = {
    total_documents: plotDocuments.length, total_queries: queryCount,
    avg_confidence: plotDocuments.length ? plotDocuments.reduce((sum, doc) => sum + (doc.source_confidence ?? 0), 0) / plotDocuments.length : 0,
    pending_review: plotQueue.length, graph_nodes: graph.nodes.length, graph_edges: graph.edges.length,
  };

  async function createPlot(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const plot = await backendFetch<Plot>("plots/", { method: "POST", body: JSON.stringify({ name: String(form.get("name")), crop_type: String(form.get("crop_type")), size_ha: Number(form.get("size_ha")) }) });
      await refreshWorkspace(); setActivePlotId(plot.id); setShowCreatePlot(false);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create the field."); }
  }

  function navigateToQuery(question: string) { setPendingQuery(question); setSection("query"); }
  function changeSection(value: string) { setSection(value as Section); if (value !== "query") setPendingQuery(undefined); }

  if (loading) return <div className={styles.main} style={{ marginLeft: 0, padding: 32 }}>Loading your farm…</div>;
  if (!farm) return <div className={styles.main} style={{ marginLeft: 0, padding: 32 }}><h1>Could not load your farm</h1><p role="alert">{error}</p><button className="btn btn-secondary" onClick={() => void refreshWorkspace().catch(cause => setError(String(cause)))}>Retry</button><button className="btn btn-ghost" onClick={onLogout}>Sign out</button></div>;

  return <div className={styles.layout}>
    <Sidebar farm={farm} activePlot={activePlot ?? { id: "", farm_id: farm.id, name: "No field", crop_type: "", size_ha: 1, created_at: "" }} onPlotChange={plot => { setActivePlotId(plot.id); setSection("dashboard"); }} activeSection={section} onSectionChange={changeSection} pendingCount={queue.length} onResetDemo={() => undefined} user={user} onLogout={onLogout} />
    <main className={styles.main}>
      <div style={{ padding: "9px 24px", color: "#bbf7d0", background: "#173322", fontSize: 12 }}>Signed in as {user.email} · {user.role} · connected to live farm data</div>
      {error && <div role="alert" style={{ margin: 16, padding: 12, border: "1px solid #7f1d1d", color: "#fecaca", borderRadius: 8 }}>{error}<button className="btn btn-ghost" onClick={() => setError(null)}>Dismiss</button></div>}
      {!activePlot ? <section style={{ padding: 32, maxWidth: 540 }}><h1>Create your first field</h1><p>Add a crop field to begin storing farm records.</p><button className="btn btn-primary" onClick={() => setShowCreatePlot(true)}>Add a field</button>{showCreatePlot && <form onSubmit={createPlot} style={{ display: "grid", gap: 12, marginTop: 18 }}><label>Field name<input name="name" required maxLength={255} /></label><label>Crop type<input name="crop_type" required maxLength={255} /></label><label>Size (hectares)<input name="size_ha" type="number" min="0.01" step="0.01" required /></label><button className="btn btn-primary">Create field</button></form>}</section>
        : <>
          {section === "dashboard" && <DashboardView stats={stats} plot={activePlot} documents={plotDocuments} onAskQuery={navigateToQuery} />}
          {section === "query" && <QueryView key={`${activePlot.id}:${pendingQuery ?? ""}`} initialQuery={pendingQuery} plotId={activePlot.id} plotName={activePlot.name} userRole={user.role} documents={plotDocuments} suggestedQueries={[`What records are available for ${activePlot.name}?`, `What are the latest field events for ${activePlot.name}?`, `What evidence is recorded for ${activePlot.name}?`]} onQueryComplete={() => setQueryCount(count => count + 1)} />}
          {section === "timeline" && <TimelineView events={timelineEvents} plot={activePlot} />}
          {section === "graph" && <GraphView key={activePlot.id} nodes={graph.nodes} edges={graph.edges} />}
          {section === "capture" && <LiveCaptureView plot={activePlot} queue={plotQueue} documents={plotDocuments} onRefresh={refreshWorkspace} />}
        </>}
    </main>
  </div>;
}
