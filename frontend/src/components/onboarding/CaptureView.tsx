"use client";
import React, { useState } from "react";
import type { IngestionQueueItem, Document } from "@/types";
import styles from "./CaptureView.module.css";
import { Upload, FileText, CheckCircle, XCircle, Clock, AlertTriangle, Camera, FilePlus } from "lucide-react";

interface Props {
  queue: IngestionQueueItem[];
  documents: Document[];
}

export default function CaptureView({ queue: initialQueue, documents }: Props) {
  const [queue, setQueue] = useState(initialQueue);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadDone, setUploadDone] = useState(false);

  function approve(id: string) {
    setQueue(q => q.map(item => item.id === id ? { ...item, status: "approved" } : item));
  }
  function reject(id: string) {
    setQueue(q => q.map(item => item.id === id ? { ...item, status: "rejected" } : item));
  }

  async function handleFileDrop(e: React.DragEvent) {
    e.preventDefault(); setDragOver(false);
    setUploading(true);
    await new Promise(r => setTimeout(r, 2000));
    setUploading(false); setUploadDone(true);
    setTimeout(() => setUploadDone(false), 3000);
  }

  const pending = queue.filter(i => i.status === "pending");
  const resolved = queue.filter(i => i.status !== "pending");

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Ingest & Review</h1>
          <p className={styles.subtitle}>Upload documents or photos — high-confidence OCR auto-ingests; low-confidence routes here for your review before entering the graph.</p>
        </div>
      </div>

      {/* Upload zone */}
      <div
        className={`${styles.dropZone} ${dragOver ? styles.dropZoneActive : ""} ${uploading ? styles.dropZoneUploading : ""}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleFileDrop}
        onClick={() => {}}
      >
        {uploading ? (
          <div className={styles.uploadingState}>
            <div className={styles.uploadSpinner} />
            <span>Processing with OCR…</span>
          </div>
        ) : uploadDone ? (
          <div className={styles.uploadDone}>
            <CheckCircle size={28} color="var(--green-400)" />
            <span>Document ingested successfully (confidence ≥ 85%)</span>
          </div>
        ) : (
          <>
            <div className={styles.dropIcon}>
              <Upload size={28} color="var(--text-muted)" />
            </div>
            <div className={styles.dropText}>
              <span className={styles.dropTitle}>Drop field notes, receipts, or weather PDFs</span>
              <span className={styles.dropSub}>PDF, CSV, JPG, PNG · Max 20 MB</span>
            </div>
            <div className={styles.dropBtns}>
              <button className="btn btn-secondary" id="btn-upload-file"><FilePlus size={14} />Browse files</button>
              <button className="btn btn-secondary" id="btn-capture-photo"><Camera size={14} />Capture photo</button>
            </div>
            <div className={styles.dropRule}>
              <span className={styles.ruleBox} style={{ background: "rgba(34,197,94,0.08)", borderColor: "rgba(34,197,94,0.2)", color: "var(--green-400)" }}>
                ≥ 85% OCR confidence → Auto-ingest
              </span>
              <span className={styles.ruleBox} style={{ background: "rgba(245,158,11,0.08)", borderColor: "rgba(245,158,11,0.2)", color: "var(--amber-400)" }}>
                &lt; 85% → Human review queue
              </span>
            </div>
          </>
        )}
      </div>

      {/* Review queue */}
      {pending.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <AlertTriangle size={15} color="var(--amber-400)" />
            <h2 className={styles.sectionTitle}>Awaiting Review ({pending.length})</h2>
          </div>
          <div className={styles.queueList}>
            {pending.map(item => (
              <div key={item.id} className={styles.queueCard}>
                <div className={styles.queueTop}>
                  <div className={styles.queueIconWrap}>
                    <FileText size={14} color="var(--amber-400)" />
                  </div>
                  <div className={styles.queueInfo}>
                    <span className={styles.queueLabel}>{item.label}</span>
                    <div className={styles.queueMeta}>
                      <span>{item.source_type.toUpperCase()}</span>
                      <span>·</span>
                      <span>OCR confidence: <strong style={{ color: item.confidence >= 0.7 ? "var(--amber-400)" : "#f87171" }}>{Math.round(item.confidence * 100)}%</strong></span>
                      <span>·</span>
                      <span>{item.uploaded_at.slice(0, 10)}</span>
                    </div>
                  </div>
                  <div className={styles.queueActions}>
                    <button className={styles.approveBtn} id={`btn-approve-${item.id}`} onClick={() => approve(item.id)}>
                      <CheckCircle size={13} />Approve
                    </button>
                    <button className={styles.rejectBtn} id={`btn-reject-${item.id}`} onClick={() => reject(item.id)}>
                      <XCircle size={13} />Reject
                    </button>
                  </div>
                </div>
                <div className={styles.extractedText}>
                  <div className={styles.extractedLabel}>Extracted text (OCR output):</div>
                  <div className={styles.extractedContent}>{item.extracted_text}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Resolved */}
      {resolved.length > 0 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle} style={{ fontSize: 14 }}>Recently resolved</h2>
          {resolved.map(item => (
            <div key={item.id} className={`${styles.resolvedRow} ${item.status === "approved" ? styles.resolvedApproved : styles.resolvedRejected}`}>
              {item.status === "approved" ? <CheckCircle size={13} color="var(--green-400)" /> : <XCircle size={13} color="#f87171" />}
              <span>{item.label}</span>
              <span className={styles.resolvedStatus}>{item.status}</span>
            </div>
          ))}
        </div>
      )}

      {/* Indexed documents */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>All Documents ({documents.length})</h2>
        <div className={styles.docGrid}>
          {documents.map(doc => (
            <div key={doc.id} className={styles.docCard}>
              <div className={styles.docCardTop}>
                <span className={`${styles.docType} ${doc.source_type === "photo" ? styles.docTypePhoto : doc.source_type === "csv" ? styles.docTypeCsv : styles.docTypePdf}`}>
                  {doc.source_type.toUpperCase()}
                </span>
                {doc.ingest_status === "ready" ? (
                  <span className={styles.statusTag} style={{ color: "var(--green-400)" }}><CheckCircle size={10} />Indexed</span>
                ) : doc.ingest_status === "review_needed" ? (
                  <span className={styles.statusTag} style={{ color: "var(--amber-400)" }}><Clock size={10} />Review</span>
                ) : (
                  <span className={styles.statusTag} style={{ color: "var(--text-muted)" }}>Processing</span>
                )}
              </div>
              <div className={styles.docCardLabel}>{doc.label}</div>
              <div className={styles.docCardMeta}>
                {doc.date_of_event ?? doc.uploaded_at.slice(0, 10)}
                {doc.source_confidence != null && ` · ${Math.round(doc.source_confidence * 100)}% conf`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
