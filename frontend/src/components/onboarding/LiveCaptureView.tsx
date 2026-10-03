"use client";
import React, { useMemo, useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle, Download, FilePlus, FileText, RefreshCw, Search, Upload, XCircle } from "lucide-react";
import type { Document, IngestionQueueItem, Plot } from "@/types";
import { backendFetch } from "@/lib/api";
import styles from "./CaptureView.module.css";
import SampleDocuments from "./SampleDocuments";
import type { SampleDocument } from "@/data/sample-documents";

interface Props {
  plot: Plot;
  queue: IngestionQueueItem[];
  documents: Document[];
  onRefresh: () => Promise<void>;
}

export default function LiveCaptureView({ plot, queue, documents, onRefresh }: Props) {
  const picker = useRef<HTMLInputElement>(null);
  const cameraPicker = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const pending = queue.filter(item => item.status === "pending");
  const filteredDocuments = useMemo(() => documents.filter(document => {
    const matchesSearch = `${document.label} ${document.source_type}`.toLowerCase().includes(search.trim().toLowerCase());
    const status = document.ingest_status;
    const matchesStatus = statusFilter === "all" || (statusFilter === "review" && ["pending_review", "review_needed"].includes(status)) || (statusFilter === "processing" && ["pending_ocr", "processing"].includes(status)) || (statusFilter === "ready" && status === "ready") || (statusFilter === "failed" && status === "ingest_failed");
    return matchesSearch && matchesStatus;
  }), [documents, search, statusFilter]);

  function exportDocuments() {
    const rows = [["Label", "Type", "Status", "Uploaded", "Event date", "Confidence"], ...filteredDocuments.map(document => [document.label, document.source_type, document.ingest_status, document.uploaded_at, document.date_of_event ?? "", String(document.source_confidence ?? "")])];
    const csv = rows.map(row => row.map(value => `"${value.replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = window.document.createElement("a"); anchor.href = url; anchor.download = `${plot.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-records.csv`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function downloadDocument(documentId: string) {
    const tab = window.open("", "_blank");
    if (tab) tab.opener = null;
    setError(null);
    try {
      const result = await backendFetch<{ url: string }>(`documents/${encodeURIComponent(documentId)}/url`);
      if (tab) tab.location.href = result.url;
      else setMessage("Your browser blocked the download window. Allow pop-ups and try again.");
    } catch (cause) { tab?.close(); setError(cause instanceof Error ? cause.message : "Could not create the document download."); }
  }

  async function uploadFiles(files: File[], samples?: SampleDocument[]) {
    if (!files.length || busy) return;
    setError(null); setMessage(null); setBusy(true);
    const failures: string[] = [];
    let saved = 0;
    try {
      for (const [index, file] of files.entries()) {
        setMessage(`Uploading ${index + 1} of ${files.length}: ${file.name}`);
        try {
          if (!file.size) throw new Error("File is empty.");
          if (file.size > 20 * 1024 * 1024) throw new Error("File exceeds the 20 MB upload limit.");
          const form = new FormData();
          form.set("file", file); form.set("plot_id", plot.id);
          form.set("label", samples?.[index]?.label ?? file.name);
          if (samples?.[index]?.date) form.set("date_of_event", samples[index].date);
          const response = await backendFetch<{ ingest_status: string }>("documents/upload", { method: "POST", body: form });
          if (response.ingest_status === "ingest_failed") throw new Error("Saved, but processing failed. Check the document status.");
          saved++;
        } catch (cause) { failures.push(`${file.name}: ${cause instanceof Error ? cause.message : "Upload failed."}`); }
      }
      setMessage(`${saved} of ${files.length} documents accepted. Processing status refreshes automatically. Exact duplicates reuse the existing record.`);
      await onRefresh();
    } catch (cause) { failures.push(cause instanceof Error ? cause.message : "Could not refresh documents."); }
    finally {
      setError(failures.length ? failures.join(" ") : null); setBusy(false);
      if (picker.current) picker.current.value = ""; if (cameraPicker.current) cameraPicker.current.value = "";
    }
  }

  async function importSamples(samples: SampleDocument[]) {
    if (busy) return;
    setBusy(true); setError(null); setMessage("Preparing synthetic sample documents…");
    let files: File[];
    try {
      files = await Promise.all(samples.map(async sample => {
        const response = await fetch(`/sample-documents/${sample.filename}`);
        if (!response.ok) throw new Error(`Could not load ${sample.filename}.`);
        return new File([await response.blob()], sample.filename, { type: "text/csv" });
      }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load sample pack."); setBusy(false); return; }
    // uploadFiles owns the upload state and reports individual failures.
    setBusy(false);
    await uploadFiles(files, samples);
  }

  async function refresh() {
    setError(null);
    try { await onRefresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Refresh failed."); }
  }

  async function decide(item: IngestionQueueItem, action: "approve" | "reject") {
    setError(null); setBusy(true);
    try {
      await backendFetch(`documents/${encodeURIComponent(item.document_id)}/${action}`, { method: "POST", body: JSON.stringify({ action }) });
      setMessage(action === "approve" ? "Document approved and queued for processing." : "Document rejected.");
      await onRefresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save the review decision."); }
    finally { setBusy(false); }
  }

  return <div className={styles.container}>
    <input ref={picker} type="file" multiple accept=".pdf,.csv,.jpg,.jpeg,.png,.tif,.tiff,.webp" hidden onChange={event => void uploadFiles(Array.from(event.target.files ?? []))} />
    <input ref={cameraPicker} type="file" accept="image/*" capture="environment" hidden onChange={event => void uploadFiles(Array.from(event.target.files ?? []))} />
    <header className={styles.header}><div><h1 className={styles.title}>Ingest &amp; Review</h1><p className={styles.subtitle}>Uploads are stored and processed by your farm&apos;s configured backend.</p></div></header>
    <div className={styles.dropZone} aria-busy={busy}>
      <div className={styles.dropIcon}><Upload size={28} color="var(--text-muted)" /></div>
      <div className={styles.dropText}><span className={styles.dropTitle}>{busy ? "Working…" : `Add records to ${plot.name}`}</span><span className={styles.dropSub}>PDF, CSV, or photo · Max 20 MB</span></div>
      <div className={styles.dropBtns}>
        <button className="btn btn-secondary" onClick={() => picker.current?.click()} disabled={busy}><FilePlus size={14} />Browse files</button>
        <button className="btn btn-secondary" onClick={() => cameraPicker.current?.click()} disabled={busy}><Camera size={14} />Take photo</button>
      </div>
    </div>
    <SampleDocuments busy={busy} onImport={importSamples} />
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    <section className={styles.section}>
      <div className={styles.sectionHeader}><AlertTriangle size={15} color="var(--amber-400)" /><h2 className={styles.sectionTitle}>Awaiting Review ({pending.length})</h2></div>
      {pending.length === 0 ? <p className={styles.subtitle}>No documents need review for this field.</p> : <div className={styles.queueList}>{pending.map(item => <article key={item.document_id} className={styles.queueCard}>
        <div className={styles.queueTop}><div className={styles.queueIconWrap}><FileText size={14} color="var(--amber-400)" /></div><div className={styles.queueInfo}><span className={styles.queueLabel}>{item.label}</span><div className={styles.queueMeta}><span>{item.source_type.toUpperCase()}</span><span>·</span><span>{item.uploaded_at.slice(0, 10)}</span></div></div>
          <div className={styles.queueActions}><button className={styles.approveBtn} disabled={busy} onClick={() => void decide(item, "approve")}><CheckCircle size={13} />Approve</button><button className={styles.rejectBtn} disabled={busy} onClick={() => void decide(item, "reject")}><XCircle size={13} />Reject</button></div></div>
        <div className={styles.extractedText}><div className={styles.extractedLabel}>Extracted text</div><div className={styles.extractedContent}>{item.extracted_text || "Text extraction is still running or returned no text."}</div></div>
      </article>)}</div>}
    </section>
    <section className={styles.section}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}><h2 className={styles.sectionTitle}>Documents ({filteredDocuments.length}{filteredDocuments.length !== documents.length ? ` of ${documents.length}` : ""})</h2><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button className="btn btn-secondary" onClick={() => void refresh()} disabled={busy}><RefreshCw size={14} />Refresh</button><button className="btn btn-secondary" onClick={exportDocuments} disabled={!filteredDocuments.length}><Download size={14} />Export CSV</button></div></div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><label style={{ position: "relative", flex: "1 1 220px" }}><Search size={14} style={{ position: "absolute", top: 12, left: 11, color: "var(--text-muted)" }} /><input aria-label="Search documents" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search records…" style={{ width: "100%", padding: "9px 12px 9px 32px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }} /></label><select aria-label="Filter document status" value={statusFilter} onChange={event => setStatusFilter(event.target.value)} style={{ padding: "9px 12px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}><option value="all">All statuses</option><option value="review">Needs review</option><option value="processing">Processing</option><option value="ready">Ready</option><option value="failed">Failed</option></select></div>
      {filteredDocuments.length ? <div className={styles.docGrid}>{filteredDocuments.map(document => <article key={document.id} className={styles.docCard}>
        <div className={styles.docCardTop}><span className={`${styles.docType} ${document.source_type === "photo" ? styles.docTypePhoto : document.source_type === "csv" ? styles.docTypeCsv : styles.docTypePdf}`}>{document.source_type.toUpperCase()}</span><span className={styles.statusTag}>{document.ingest_status.replaceAll("_", " ")}</span></div>
        <div className={styles.docCardLabel}>{document.label}</div><div className={styles.docCardMeta}>{document.date_of_event ?? document.uploaded_at.slice(0, 10)}</div>
        <button className="btn btn-ghost" style={{ alignSelf: "flex-start", padding: "6px 8px", fontSize: 12 }} onClick={() => void downloadDocument(document.id)}><Download size={13} />Download original</button>
      </article>)}</div> : <p>No documents match those filters.</p>}
    </section>
  </div>;
}
