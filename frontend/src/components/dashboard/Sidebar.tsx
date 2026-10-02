"use client";
import React, { useState } from "react";
import styles from "./Sidebar.module.css";
import type { Farm, Plot, User } from "@/types";
import FarmSettings from "@/components/dashboard/FarmSettings";
import {
  Leaf, LayoutDashboard, Search, Clock, Upload,
  GitBranch, ChevronDown, ChevronRight, Settings,
  Bell, HelpCircle, Zap, X, RotateCcw, LogOut, Plus, Pencil
} from "lucide-react";

interface Props {
  farm: Farm;
  activePlot: Plot;
  onPlotChange: (p: Plot) => void;
  activeSection: string;
  onSectionChange: (s: string) => void;
  pendingCount: number;
  onResetDemo: () => void;
  user?: User;
  onLogout?: () => void;
  onCreatePlot?: () => void;
  onEditPlot?: (plot: Plot) => void;
  onFarmUpdated?: (name: string) => void;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "query", label: "Ask Aegis", icon: Search },
  { id: "timeline", label: "Field Timeline", icon: Clock },
  { id: "graph", label: "Knowledge Graph", icon: GitBranch },
  { id: "capture", label: "Ingest & Review", icon: Upload },
];

export default function Sidebar({ farm, activePlot, onPlotChange, activeSection, onSectionChange, pendingCount, onResetDemo, user, onLogout, onCreatePlot, onEditPlot, onFarmUpdated }: Props) {
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
          <span className={styles.sectionLabel}>Fields ({farm.plots.length})</span>
          {plotsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        {plotsOpen && (
          <div className={styles.plotList}>
            {user && <button className={styles.bottomNavItem} onClick={onCreatePlot} style={{ margin: "0 4px 4px", width: "calc(100% - 8px)" }}><Plus size={14} /><span>Add field</span></button>}
            {farm.plots.map(plot => (
              <div key={plot.id} style={{ display: "flex", alignItems: "center" }}>
                <button className={`${styles.plotItem} ${activePlot.id === plot.id ? styles.plotItemActive : ""}`} onClick={() => onPlotChange(plot)} style={{ flex:  1, minWidth: 0 }}>
                  <div className={`${styles.plotDot} ${activePlot.id === plot.id ? styles.plotDotActive : ""}`} />
                  <div className={styles.plotInfo}><span className={styles.plotName}>{plot.name}</span><span className={styles.plotMeta}>{plot.crop_type} · {plot.size_ha} ha</span></div>
                </button>
                {user && <button aria-label={`Edit ${plot.name}`} title={`Edit ${plot.name}`} className={styles.bottomNavItem} style={{ width: "auto", padding: 7 }} onClick={() => onEditPlot?.(plot)}><Pencil size={13} /></button>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bottom */}
      <div className={styles.bottom}>
        <div className={styles.upgradeCard}>
          <Zap size={14} color="var(--amber-400)" />
          <span>{user ? `Live farm · ${farm.plots.length} fields` : `Local demo · ${farm.plots.length} fields`}</span>
        </div>
        <div className={styles.bottomNav}>
          <button className={styles.bottomNavItem} onClick={() => { setPanel("alerts"); onSectionChange("capture"); }}><Bell size={15} /><span>Alerts{pendingCount ? ` (${pendingCount})` : ""}</span></button>
          <button className={styles.bottomNavItem} onClick={() => setPanel("help")}><HelpCircle size={15} /><span>Help</span></button>
          <button className={styles.bottomNavItem} onClick={() => setPanel("settings")}><Settings size={15} /><span>Settings</span></button>
          {user && <button className={styles.bottomNavItem} onClick={onLogout}><LogOut size={15} /><span>Sign out · {user.email}</span></button>}
        </div>
      </div>
      {panel && <div role="dialog" aria-modal="true" aria-labelledby="sidebar-dialog-title" style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(0,0,0,.55)", display: "grid", placeItems: "center", padding: 20 }} onClick={() => setPanel(null)}>
          <div style={{ width: "min(480px, 100%)", maxHeight: "90vh", overflowY: "auto", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 14, padding: 22, color: "var(--text-primary)" }} onClick={event => event.stopPropagation()}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><h2 id="sidebar-dialog-title" style={{ margin: 0 }}>{panel === "alerts" ? "Review alerts" : panel === "help" ? "Help" : "Settings"}</h2><button aria-label="Close" onClick={() => setPanel(null)} className={styles.bottomNavItem} style={{ width: "auto", padding: 6 }}><X size={16} /></button></div>
          {panel === "alerts" && <p>{pendingCount ? `${pendingCount} document${pendingCount === 1 ? " is" : "s are"} waiting for review in Ingest & Review.` : "No documents are waiting for review."}</p>}
          {panel === "help" && <div><p>Choose a field, then open its dashboard, record timeline, knowledge graph, or query view.</p>{user ? <p>Your account is connected to the farm API. Upload processing and AI answers depend on the services configured by the farm administrator.</p> : <p>Sample preview changes are stored in this browser. No real account or farm data is used.</p>}</div>}
          {panel === "settings" && (user ? <FarmSettings farm={farm} user={user} onFarmUpdated={name => onFarmUpdated?.(name)} /> : <div><p>Reset this browser&apos;s demo changes and restore the original sample records.</p><button className="btn btn-secondary" onClick={() => { onResetDemo(); setPanel(null); }}><RotateCcw size={14} />Reset demo data</button></div>)}
        </div>
      </div>}
    </aside>
  );
}
