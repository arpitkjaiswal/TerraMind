"use client";
import React, { useState } from "react";
import styles from "./Sidebar.module.css";
import type { Farm, Plot } from "@/types";
import {
  Leaf, LayoutDashboard, Search, Clock, Upload,
  GitBranch, ChevronDown, ChevronRight, Settings,
  Bell, HelpCircle, Zap, X, RotateCcw
} from "lucide-react";

interface Props {
  farm: Farm;
  activePlot: Plot;
  onPlotChange: (p: Plot) => void;
  activeSection: string;
  onSectionChange: (s: string) => void;
  pendingCount: number;
  onResetDemo: () => void;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "query", label: "Ask Aegis", icon: Search },
  { id: "timeline", label: "Field Timeline", icon: Clock },
  { id: "graph", label: "Knowledge Graph", icon: GitBranch },
  { id: "capture", label: "Ingest & Review", icon: Upload },
];

export default function Sidebar({ farm, activePlot, onPlotChange, activeSection, onSectionChange, pendingCount, onResetDemo }: Props) {
  const [plotsOpen, setPlotsOpen] = useState(true);
  const [panel, setPanel] = useState<"alerts" | "help" | "settings" | null>(null);

  return (
    <aside className={styles.sidebar}>
      {/* Logo */}
      <div className={styles.logo}>
        <div className={styles.logoIcon}>
          <Leaf size={18} strokeWidth={2.5} />
        </div>
        <div>
          <span className={styles.logoText}>Aegis</span>
          <span className={styles.logoBeta}>BETA</span>
        </div>
      </div>

      {/* Farm selector */}
      <div className={styles.farmBadge}>
        <div className={styles.farmDot} />
        <span className={styles.farmName}>{farm.name}</span>
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            id={`nav-${id}`}
            className={`${styles.navItem} ${activeSection === id ? styles.navItemActive : ""}`}
            onClick={() => onSectionChange(id)}
          >
            <Icon size={16} strokeWidth={2} />
            <span>{label}</span>
            {id === "query" && <span className={styles.navBadge}>AI</span>}
          </button>
        ))}
      </nav>

      <div className={styles.divider} />

      {/* Plot switcher */}
      <div className={styles.section}>
        <button className={styles.sectionHeader} onClick={() => setPlotsOpen(o => !o)}>
          <span className={styles.sectionLabel}>Fields</span>
          {plotsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        {plotsOpen && (
          <div className={styles.plotList}>
            {farm.plots.map(plot => (
              <button
                key={plot.id}
                className={`${styles.plotItem} ${activePlot.id === plot.id ? styles.plotItemActive : ""}`}
                onClick={() => onPlotChange(plot)}
              >
                <div className={`${styles.plotDot} ${activePlot.id === plot.id ? styles.plotDotActive : ""}`} />
                <div className={styles.plotInfo}>
                  <span className={styles.plotName}>{plot.name}</span>
                  <span className={styles.plotMeta}>{plot.crop_type} · {plot.size_ha} ha</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Bottom */}
      <div className={styles.bottom}>
        <div className={styles.upgradeCard}>
          <Zap size={14} color="var(--amber-400)" />
          <span>Local demo — {farm.plots.length} fields</span>
        </div>
        <div className={styles.bottomNav}>
          <button className={styles.bottomNavItem} onClick={() => { setPanel("alerts"); onSectionChange("capture"); }}><Bell size={15} /><span>Alerts{pendingCount ? ` (${pendingCount})` : ""}</span></button>
          <button className={styles.bottomNavItem} onClick={() => setPanel("help")}><HelpCircle size={15} /><span>Help</span></button>
          <button className={styles.bottomNavItem} onClick={() => setPanel("settings")}><Settings size={15} /><span>Settings</span></button>
        </div>
      </div>
      {panel && <div role="dialog" aria-modal="true" aria-labelledby="sidebar-dialog-title" style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(0,0,0,.55)", display: "grid", placeItems: "center", padding: 20 }} onClick={() => setPanel(null)}>
        <div style={{ width: "min(440px, 100%)", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 14, padding: 22, color: "var(--text-primary)" }} onClick={event => event.stopPropagation()}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><h2 id="sidebar-dialog-title" style={{ margin: 0 }}>{panel === "alerts" ? "Review alerts" : panel === "help" ? "Help" : "Demo settings"}</h2><button aria-label="Close" onClick={() => setPanel(null)} className={styles.bottomNavItem} style={{ width: "auto", padding: 6 }}><X size={16} /></button></div>
          {panel === "alerts" && <p>{pendingCount ? `${pendingCount} document${pendingCount === 1 ? " is" : "s are"} waiting for review in Ingest & Review.` : "No documents are waiting for review."}</p>}
          {panel === "help" && <div><p>Choose a field, then explore its dashboard, record timeline, knowledge graph, or query its sample record index.</p><p>Uploads, review decisions, and query counts are saved in this browser only. The demo does not run OCR or connect to a live agronomy service.</p></div>}
          {panel === "settings" && <div><p>Reset this browser&apos;s demo changes and restore the original sample records.</p><button className="btn btn-secondary" onClick={() => { onResetDemo(); setPanel(null); }}><RotateCcw size={14} />Reset demo data</button></div>}
        </div>
      </div>}
    </aside>
  );
}
