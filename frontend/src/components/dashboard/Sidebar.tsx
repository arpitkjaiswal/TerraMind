"use client";
import React, { useState } from "react";
import styles from "./Sidebar.module.css";
import type { Farm, Plot } from "@/types";
import {
  Leaf, LayoutDashboard, Search, Clock, Upload,
  GitBranch, ChevronDown, ChevronRight, Settings,
  Bell, HelpCircle, Zap
} from "lucide-react";

interface Props {
  farm: Farm;
  activePlot: Plot;
  onPlotChange: (p: Plot) => void;
  activeSection: string;
  onSectionChange: (s: string) => void;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "query", label: "Ask Aegis", icon: Search },
  { id: "timeline", label: "Field Timeline", icon: Clock },
  { id: "graph", label: "Knowledge Graph", icon: GitBranch },
  { id: "capture", label: "Ingest & Review", icon: Upload },
];

export default function Sidebar({ farm, activePlot, onPlotChange, activeSection, onSectionChange }: Props) {
  const [plotsOpen, setPlotsOpen] = useState(true);

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
          <span>Free plan — 1 plot</span>
        </div>
        <div className={styles.bottomNav}>
          <button className={styles.bottomNavItem}><Bell size={15} /><span>Alerts</span></button>
          <button className={styles.bottomNavItem}><HelpCircle size={15} /><span>Help</span></button>
          <button className={styles.bottomNavItem}><Settings size={15} /><span>Settings</span></button>
        </div>
      </div>
    </aside>
  );
}
