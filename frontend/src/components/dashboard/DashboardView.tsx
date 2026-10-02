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
    { label: "Sample Documents", value: stats.total_documents, icon: FileText, color: "var(--sky-400)", trend: "This field" },
    { label: "Demo Queries", value: stats.total_queries, icon: Search, color: "var(--green-400)", trend: "Browser count" },
    { label: "Graph Nodes", value: stats.graph_nodes, icon: Network, color: "var(--amber-400)", trend: `${stats.graph_edges} links` },
    { label: "Pending Review", value: stats.pending_review, icon: AlertTriangle, color: "#f87171", trend: "Local queue" },
  ];

  const readyDocs = documents.filter(d => d.ingest_status === "ready");
  const reviewDocs = documents.filter(d => d.ingest_status === "review_needed");

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>{plot.name}</h1>
          <p className={styles.subtitle}>{plot.crop_type} &middot; {plot.size_ha} ha &middot; Local demo records</p>
        </div>
        <div className={styles.headerBadge}>
          <Activity size={13} />
          <span>Demo data</span>
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
      {plot.id === "plot-B" && <div className={styles.yieldBanner}>
        <div className={styles.yieldLeft}>
          <TrendingDown size={20} color="#f87171" />
          <div>
            <div className={styles.yieldTitle}>Sample yield record</div>
            <div className={styles.yieldDesc}>The demo dataset includes a 2026 Field B yield entry (6.8 t/ha) and a stated 3-year average (8.5 t/ha). These sample records do not establish a cause.</div>
          </div>
        </div>
        <button className="btn btn-primary" id="btn-ask-yield" onClick={() => onAskQuery(`What sample yield records are available for ${plot.name.split(" — ")[0]}?`)}>
          View records →
        </button>
      </div>}

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
                ) : doc.ingest_status === "ingest_failed" ? (
                  <span className={styles.statusReview}><AlertTriangle size={12} />Rejected</span>
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
            `What sample records are available for ${plot.name.split(" — ")[0]}?`,
            `What chemicals are listed for ${plot.name.split(" — ")[0]}?`,
            `What yield records are listed for ${plot.name.split(" — ")[0]}?`,
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
