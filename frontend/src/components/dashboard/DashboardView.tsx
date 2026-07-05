"use client";
import React from "react";
import type { DashboardStats, Plot, Document } from "@/types";
import { FileText, Search, Activity, AlertTriangle, Network, TrendingDown, CheckCircle } from "lucide-react";
import styles from "./DashboardView.module.css";

interface Props {
  stats: DashboardStats;
  plot: Plot;
  documents: Document[];
  onAskQuery: (q: string) => void;
}



export default function DashboardView({ stats, plot, documents, onAskQuery }: Props) {
  const statCards = [
    { label: "Documents Ingested", value: stats.total_documents, icon: FileText, color: "var(--sky-400)", trend: "+3 this season" },
    { label: "Queries Run", value: stats.total_queries, icon: Search, color: "var(--green-400)", trend: "Avg 84ms" },
    { label: "Graph Nodes", value: stats.graph_nodes, icon: Network, color: "var(--amber-400)", trend: `${stats.graph_edges} edges` },
    { label: "Pending Review", value: stats.pending_review, icon: AlertTriangle, color: "#f87171", trend: "2 OCR uploads" },
  ];

  const readyDocs = documents.filter(d => d.ingest_status === "ready");
  const reviewDocs = documents.filter(d => d.ingest_status === "review_needed");

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>{plot.name}</h1>
          <p className={styles.subtitle}>{plot.crop_type} &middot; {plot.size_ha} ha &middot; Soil memory active</p>
        </div>
        <div className={styles.headerBadge}>
          <Activity size={13} />
          <span>Graph live</span>
        </div>
      </div>

      {/* Stat cards */}
      <div className={styles.statsGrid}>
        {statCards.map(({ label, value, icon: Icon, color, trend }) => (
          <div key={label} className={styles.statCard}>
            <div className={styles.statTop}>
              <div className={styles.statIconWrap} style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
                <Icon size={16} color={color} strokeWidth={2} />
              </div>
              <span className={styles.statTrend}>{trend}</span>
            </div>
            <div className={styles.statValue}>{value}</div>
            <div className={styles.statLabel}>{label}</div>
          </div>
        ))}
      </div>

      {/* Yield snapshot */}
      <div className={styles.yieldBanner}>
        <div className={styles.yieldLeft}>
          <TrendingDown size={20} color="#f87171" />
          <div>
            <div className={styles.yieldTitle}>2026 Yield Anomaly Detected</div>
            <div className={styles.yieldDesc}>Field B recorded 6.8 t/ha vs 8.5 t/ha 3-year average — a 20% shortfall. Multi-hop graph path identified.</div>
          </div>
        </div>
        <button className="btn btn-primary" id="btn-ask-yield" onClick={() => onAskQuery("Why did Field B's yield drop by 20% in 2026?")}>
          Investigate →
        </button>
      </div>

      {/* Recent documents */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Recent Documents</h2>
          <span className={styles.sectionMeta}>{readyDocs.length} indexed · {reviewDocs.length} awaiting review</span>
        </div>
        <div className={styles.docList}>
          {documents.slice(0, 5).map(doc => (
            <div key={doc.id} className={styles.docRow}>
              <div className={styles.docIcon}>
                <FileText size={13} color={doc.source_type === "photo" ? "var(--amber-400)" : "var(--sky-400)"} />
              </div>
              <div className={styles.docInfo}>
                <span className={styles.docLabel}>{doc.label}</span>
                <span className={styles.docMeta}>{doc.source_type.toUpperCase()} · {doc.date_of_event ?? doc.uploaded_at.slice(0, 10)}</span>
              </div>
              <div className={styles.docStatus}>
                {doc.ingest_status === "ready" ? (
                  <span className={styles.statusReady}><CheckCircle size={12} />Ready</span>
                ) : doc.ingest_status === "review_needed" ? (
                  <span className={styles.statusReview}><AlertTriangle size={12} />Review</span>
                ) : (
                  <span className={styles.statusProc}>Processing</span>
                )}
                {doc.source_confidence != null && (
                  <span className={styles.confidence}>{Math.round(doc.source_confidence * 100)}%</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick queries */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Suggested Questions</h2>
        <div className={styles.queryChips}>
          {[
            "Why did Field B's yield drop by 20% in 2026?",
            "What chemicals were applied in the last 3 seasons?",
            "Which weather events correlate with yield changes?",
          ].map(q => (
            <button key={q} className={styles.queryChip} onClick={() => onAskQuery(q)}>
              <Search size={12} />
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
