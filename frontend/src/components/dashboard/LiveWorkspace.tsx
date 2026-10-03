"use client";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
interface GraphResponse { plot_id: string; nodes: GraphNode[]; edges: Omit<GraphEdge, "id">[]; warnings?: string[]; }

export default function LiveWorkspace({ user, onLogout }: Props) {
  const [farm, setFarm] = useState<Farm | null>(null);
  const [plots, setPlots] = useState<Plot[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [queue, setQueue] = useState<IngestionQueueItem[]>([]);
  const [activePlotId, setActivePlotId] = useState("");
  const [section, setSection] = useState<Section>("dashboard");
  const [pendingQuery, setPendingQuery] = useState<string | undefined>();
  const [queryCount, setQueryCount] = useState(0);
  const [graphResponse, setGraphResponse] = useState<GraphResponse | null>(null);
  const [graphError, setGraphError] = useState<{ plotId: string; message: string } | null>(null);
  const [graphRevision, setGraphRevision] = useState(0);
  const workspaceRequest = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [plotEditor, setPlotEditor] = useState<Plot | "new" | null>(null);

  const refreshWorkspace = useCallback(async () => {
    const request = ++workspaceRequest.current;
    const [farmRecord, plotRecords, documentRecords, queueRecords] = await Promise.all([
      backendFetch<FarmRecord>("farms/me"),
      backendFetch<Plot[]>("plots/"),
      backendFetch<Document[]>("documents/"),
      backendFetch<ReviewRecord[]>("documents/review-queue"),
    ]);
    if (request !== workspaceRequest.current) return;
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

  const documentRevision = plotDocuments.map(document => `${document.id}:${document.ingest_status}`).sort().join("|");
  const hasProcessingDocuments = documents.some(document => ["pending_ocr", "processing"].includes(document.ingest_status));
  useEffect(() => {
    if (!hasProcessingDocuments) return;
    let disposed = false;
    let timer: number;
    const poll = async () => {
      try { if (!document.hidden) await refreshWorkspace(); }
      catch (cause) { if (!disposed) setError(cause instanceof Error ? cause.message : "Document status refresh failed."); }
      finally { if (!disposed) timer = window.setTimeout(poll, 5000); }
    };
    timer = window.setTimeout(poll, 5000);
    return () => { disposed = true; window.clearTimeout(timer); };
  }, [hasProcessingDocuments, refreshWorkspace]);

  useEffect(() => {
    if (!activePlotId || (section !== "graph" && section !== "dashboard")) return;
    const controller = new AbortController();
    let timer: number;
    const refresh = async () => {
      try {
        const result = await backendFetch<GraphResponse>(`plots/${encodeURIComponent(activePlotId)}/graph`, { signal: controller.signal });
        if (result.plot_id !== activePlotId) throw new Error("Graph response did not match the selected field.");
        if (!controller.signal.aborted) { setGraphResponse(result); setGraphError(null); }
      } catch (cause) {
        if (!controller.signal.aborted) setGraphError({ plotId: activePlotId, message: cause instanceof Error ? cause.message : "Could not load the field graph." });
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(() => {
          if (!document.hidden) void refresh();
          else timer = window.setTimeout(refresh, 10000);
        }, 10000);
      }
    };
    void refresh();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [activePlotId, section, documentRevision, graphRevision]);

  useEffect(() => {
    if (!activePlotId) return;
    const controller = new AbortController();
    backendFetch<QueryHistory[]>(`query/history?plot_id=${encodeURIComponent(activePlotId)}&limit=100`, { signal: controller.signal })
      .then(rows => { if (!controller.signal.aborted) setQueryCount(rows.length); })
      .catch(() => { if (!controller.signal.aborted) setQueryCount(0); });
    return () => controller.abort();
  }, [activePlotId]);

  const graph = useMemo(() => {
    if (graphResponse?.plot_id !== activePlotId) return { nodes: [], edges: [] };
    const edges: GraphEdge[] = graphResponse.edges.map((edge, index) => ({ ...edge, id: `${edge.source}:${edge.type}:${edge.target}:${edge.source_document_id ?? ""}:${index}` }));
    return { nodes: graphResponse.nodes, edges };
  }, [graphResponse, activePlotId]);
  const stats: DashboardStats = {
    total_documents: plotDocuments.length, total_queries: queryCount,
    avg_confidence: plotDocuments.length ? plotDocuments.reduce((sum, doc) => sum + (doc.source_confidence ?? 0), 0) / plotDocuments.length : 0,
    pending_review: plotQueue.length, graph_nodes: graph.nodes.length, graph_edges: graph.edges.length,
  };

  async function createPlot(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null);
    const form = new FormData(event.currentTarget);
    const current = plotEditor && plotEditor !== "new" ? plotEditor : null;
    const body = { name: String(form.get("name")).trim(), crop_type: String(form.get("crop_type")).trim(), size_ha: Number(form.get("size_ha")) };
    try {
      const plot = await backendFetch<Plot>(current ? `plots/${encodeURIComponent(current.id)}` : "plots/", { method: current ? "PUT" : "POST", body: JSON.stringify(body) });
      await refreshWorkspace(); setActivePlotId(plot.id); setPlotEditor(null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create the field."); }
  }

  function navigateToQuery(question: string) { setPendingQuery(question); setSection("query"); }
  function changeSection(value: string) { setSection(value as Section); if (value !== "query") setPendingQuery(undefined); }

  if (loading) return <div className={styles.main} style={{ marginLeft: 0, padding: 32 }}>Loading your farm…</div>;
  if (!farm) return <div className={styles.main} style={{ marginLeft: 0, padding: 32 }}><h1>Could not load your farm</h1><p role="alert">{error}</p><button className="btn btn-secondary" onClick={() => void refreshWorkspace().catch(cause => setError(String(cause)))}>Retry</button><button className="btn btn-ghost" onClick={onLogout}>Sign out</button></div>;

  return <div className={styles.layout}>
    <Sidebar farm={farm} activePlot={activePlot ?? { id: "", farm_id: farm.id, name: "No field", crop_type: "", size_ha: 1, created_at: "" }} onPlotChange={plot => { setActivePlotId(plot.id); setSection("dashboard"); }} activeSection={section} onSectionChange={changeSection} pendingCount={queue.length} onResetDemo={() => undefined} user={user} onLogout={onLogout} onCreatePlot={() => setPlotEditor("new")} onEditPlot={plot => setPlotEditor(plot)} onFarmUpdated={name => setFarm(current => current ? { ...current, name } : current)} />
    <main className={styles.main}>
      <div style={{ padding: "9px 24px", color: "#bbf7d0", background: "#173322", fontSize: 12 }}>Signed in as {user.email} · {user.role} · connected to live farm data</div>
      {error && <div role="alert" style={{ margin: 16, padding: 12, border: "1px solid #7f1d1d", color: "#fecaca", borderRadius: 8 }}>{error}<button className="btn btn-ghost" onClick={() => setError(null)}>Dismiss</button></div>}
      {!activePlot ? <section style={{ padding: 32, maxWidth: 540 }}><h1>Create your first field</h1><p>Add a crop field to begin storing farm records.</p><button className="btn btn-primary" onClick={() => setPlotEditor("new")}>Add a field</button></section>
        : <>
          {section === "dashboard" && <DashboardView stats={stats} plot={activePlot} documents={plotDocuments} onAskQuery={navigateToQuery} />}
          {section === "query" && <QueryView key={`${activePlot.id}:${pendingQuery ?? ""}`} initialQuery={pendingQuery} plotId={activePlot.id} plotName={activePlot.name} userRole={user.role} documents={plotDocuments} suggestedQueries={[`What records are available for ${activePlot.name}?`, `What are the latest field events for ${activePlot.name}?`, `What evidence is recorded for ${activePlot.name}?`]} onQueryComplete={() => setQueryCount(count => count + 1)} />}
          {section === "timeline" && <TimelineView events={timelineEvents} plot={activePlot} />}
          {section === "graph" && <>
            <div style={{ padding: "14px 24px", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <span role="status">{graphResponse?.plot_id === activePlotId ? "Graph refreshes every 10 seconds and when document status changes." : "Loading this field’s graph…"}</span>
              <button className="btn btn-secondary" onClick={() => setGraphRevision(value => value + 1)}>Refresh graph</button>
              {graphError?.plotId === activePlotId && <p role="alert">{graphError.message}</p>}
              {graphResponse?.plot_id === activePlotId && graphResponse.warnings?.map(warning => <p role="status" key={warning}>{warning}</p>)}
            </div>
            <GraphView key={activePlot.id} nodes={graph.nodes} edges={graph.edges} />
          </>}
          {section === "capture" && <LiveCaptureView key={activePlot.id} plot={activePlot} queue={plotQueue} documents={plotDocuments} onRefresh={refreshWorkspace} />}
        </>}
      {plotEditor && <div role="presentation" onClick={() => setPlotEditor(null)} style={{ position: "fixed", inset: 0, zIndex: 120, display: "grid", placeItems: "center", padding: 20, background: "rgba(0,0,0,.7)" }}>
        <section role="dialog" aria-modal="true" aria-labelledby="field-editor-title" onClick={event => event.stopPropagation()} style={{ width: "min(480px, 100%)", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 16, padding: 24 }}>
          <h2 id="field-editor-title">{plotEditor === "new" ? "Add a field" : `Edit ${plotEditor.name}`}</h2>
          <p style={{ margin: "8px 0 18px" }}>Field details are saved to your farm account.</p>
          <form onSubmit={createPlot} style={{ display: "grid", gap: 12 }}>
            <label>Field name<input name="name" defaultValue={plotEditor === "new" ? "" : plotEditor.name} required maxLength={255} /></label>
            <label>Crop type<input name="crop_type" defaultValue={plotEditor === "new" ? "" : plotEditor.crop_type} required maxLength={255} /></label>
            <label>Size (hectares)<input name="size_ha" type="number" min="0.01" step="0.01" defaultValue={plotEditor === "new" ? "" : plotEditor.size_ha} required /></label>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 }}><button type="button" className="btn btn-ghost" onClick={() => setPlotEditor(null)}>Cancel</button><button className="btn btn-primary">{plotEditor === "new" ? "Create field" : "Save changes"}</button></div>
          </form>
        </section>
      </div>}
    </main>
  </div>;
}
