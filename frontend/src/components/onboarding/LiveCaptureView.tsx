"use client";
import React, { useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle, FilePlus, FileText, Upload, XCircle } from "lucide-react";
import type { Document, IngestionQueueItem, Plot } from "@/types";
import { backendFetch } from "@/lib/api";
import styles from "./CaptureView.module.css";

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
  const pending = queue.filter(item => item.status === "pending");

  async function upload(file?: File) {
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) { setError("File exceeds the 20 MB upload limit."); return; }
    setError(null); setMessage(null); setBusy(true);
    try {
      const form = new FormData();
      form.set("file", file);
      form.set("plot_id", plot.id);
      form.set("label", file.name);
      const response = await backendFetch<{ document_id: string; ingest_status: string; message: string }>("documents/upload", { method: "POST", body: form });
      setMessage(response.message || `Uploaded ${file.name}.`);
      await onRefresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload failed."); }
    finally { setBusy(false); if (picker.current) picker.current.value = ""; if (cameraPicker.current) cameraPicker.current.value = ""; }
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
    <input ref={picker} type="file" accept=".pdf,.csv,.jpg,.jpeg,.png,.tiff,.webp" hidden onChange={event => void upload(event.target.files?.[0])} />
    <input ref={cameraPicker} type="file" accept="image/*" capture="environment" hidden onChange={event => void upload(event.target.files?.[0])} />
    <header className={styles.header}><div><h1 className={styles.title}>Ingest &amp; Review</h1><p className={styles.subtitle}>Uploads are stored and processed by your farm&apos;s configured backend.</p></div></header>
    <div className={styles.dropZone} aria-busy={busy}>
      <div className={styles.dropIcon}><Upload size={28} color="var(--text-muted)" /></div>
      <div className={styles.dropText}><span className={styles.dropTitle}>{busy ? "Working…" : `Add records to ${plot.name}`}</span><span className={styles.dropSub}>PDF, CSV, or photo · Max 20 MB</span></div>
      <div className={styles.dropBtns}>
        <button className="btn btn-secondary" onClick={() => picker.current?.click()} disabled={busy}><FilePlus size={14} />Browse files</button>
        <button className="btn btn-secondary" onClick={() => cameraPicker.current?.click()} disabled={busy}><Camera size={14} />Take photo</button>
      </div>
    </div>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    <section className={styles.section}>
      <div className={styles.sectionHeader}><AlertTriangle size={15} color="var(--amber-400)" /><h2 className={styles.sectionTitle}>Awaiting Review ({pending.length})</h2></div>
      {pending.length === 0 ? <p className={styles.subtitle}>No documents need review for this field.</p> : <div className={styles.queueList}>{pending.map(item => <article key={item.document_id} className={styles.queueCard}>
        <div className={styles.queueTop}><div className={styles.queueIconWrap}><FileText size={14} color="var(--amber-400)" /></div><div className={styles.queueInfo}><span className={styles.queueLabel}>{item.label}</span><div className={styles.queueMeta}><span>{item.source_type.toUpperCase()}</span><span>·</span><span>{item.uploaded_at.slice(0, 10)}</span></div></div>
          <div className={styles.queueActions}><button className={styles.approveBtn} disabled={busy} onClick={() => void decide(item, "approve")}><CheckCircle size={13} />Approve</button><button className={styles.rejectBtn} disabled={busy} onClick={() => void decide(item, "reject")}><XCircle size={13} />Reject</button></div></div>
        <div className={styles.extractedText}><div className={styles.extractedLabel}>Extracted text</div><div className={styles.extractedContent}>{item.extracted_text || "Text extraction is still running or returned no text."}</div></div>
      </article>)}</div>}
    </section>
    <section className={styles.section}><h2 className={styles.sectionTitle}>Documents ({documents.length})</h2><div className={styles.docGrid}>{documents.map(document => <article key={document.id} className={styles.docCard}>
      <div className={styles.docCardTop}><span className={`${styles.docType} ${document.source_type === "photo" ? styles.docTypePhoto : document.source_type === "csv" ? styles.docTypeCsv : styles.docTypePdf}`}>{document.source_type.toUpperCase()}</span><span className={styles.statusTag}>{document.ingest_status.replaceAll("_", " ")}</span></div>
      <div className={styles.docCardLabel}>{document.label}</div><div className={styles.docCardMeta}>{document.date_of_event ?? document.uploaded_at.slice(0, 10)}</div>
    </article>)}</div></section>
  </div>;
}
