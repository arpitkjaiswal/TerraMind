"use client";
import React, { useState } from "react";
import type { TimelineEvent, Plot } from "@/types";
import styles from "./TimelineView.module.css";
import { Beaker, Cloud, Sprout, BarChart2, Wrench, Filter } from "lucide-react";

interface Props {
  events: TimelineEvent[];
  plot: Plot;
}

const CATEGORY_META = {
  chemical: { label: "Chemical", icon: Beaker, color: "#f59e0b", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.25)" },
  weather:  { label: "Weather",  icon: Cloud,  color: "#38bdf8", bg: "rgba(56,189,248,0.1)",  border: "rgba(56,189,248,0.25)"  },
  crop:     { label: "Crop",     icon: Sprout,  color: "#22c55e", bg: "rgba(34,197,94,0.1)",  border: "rgba(34,197,94,0.25)"  },
  yield:    { label: "Yield",    icon: BarChart2, color: "#a78bfa", bg: "rgba(167,139,250,0.1)", border: "rgba(167,139,250,0.25)" },
  practice: { label: "Practice", icon: Wrench,  color: "#fb923c", bg: "rgba(251,146,60,0.1)", border: "rgba(251,146,60,0.25)" },
};

type Category = keyof typeof CATEGORY_META;

export default function TimelineView({ events, plot }: Props) {
  const [filter, setFilter] = useState<Category | "all">("all");
  const filtered = filter === "all" ? events : events.filter(e => e.category === filter);
  const grouped: Record<string, TimelineEvent[]> = {};
  filtered.forEach(e => {
    const yr = e.date.slice(0, 4);
    if (!grouped[yr]) grouped[yr] = [];
    grouped[yr].push(e);
  });
  const years = Object.keys(grouped).sort((a, b) => Number(b) - Number(a));

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Field Timeline</h1>
          <p className={styles.subtitle}>{plot.name} · Full agronomic history from first record to present</p>
        </div>
        <div className={styles.filterRow}>
          <Filter size={13} color="var(--text-muted)" />
          {(["all", ...Object.keys(CATEGORY_META)] as Array<"all" | Category>).map(cat => (
            <button
              key={cat}
              className={`${styles.filterBtn} ${filter === cat ? styles.filterBtnActive : ""}`}
              onClick={() => setFilter(cat)}
            >
              {cat === "all" ? "All" : CATEGORY_META[cat].label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.timeline}>
        {years.map(yr => (
          <div key={yr} className={styles.yearGroup}>
            <div className={styles.yearLabel}>{yr}</div>
            <div className={styles.yearEvents}>
              {grouped[yr].sort((a, b) => a.date.localeCompare(b.date)).map((ev, idx) => {
                const meta = CATEGORY_META[ev.category];
                const Icon = meta.icon;
                return (
                  <div key={ev.id} className={`${styles.event} animate-fade-in`} style={{ animationDelay: `${idx * 60}ms` }}>
                    {/* Connector */}
                    <div className={styles.connectorCol}>
                      <div
                        className={styles.eventDot}
                        style={{ background: meta.bg, border: `2px solid ${meta.color}` }}
                      >
                        <Icon size={11} color={meta.color} strokeWidth={2.5} />
                      </div>
                      <div className={styles.connectorLine} />
                    </div>
                    {/* Card */}
                    <div className={styles.eventCard} style={{ borderColor: ev.category === "yield" && ev.description.includes("drop") ? "rgba(248,113,113,0.4)" : undefined }}>
                      <div className={styles.eventTop}>
                        <span
                          className={styles.eventCategory}
                          style={{ background: meta.bg, color: meta.color, border: `1px solid ${meta.border}` }}
                        >
                          {meta.label}
                        </span>
                        <span className={styles.eventDate}>{ev.date}</span>
                        {ev.confidence != null && ev.confidence < 1 && (
                          <span className={styles.eventConf}>{Math.round(ev.confidence * 100)}% OCR</span>
                        )}
                      </div>
                      <h3 className={styles.eventTitle}
                        style={{ color: ev.category === "yield" && ev.description.includes("drop") ? "#f87171" : undefined }}>
                        {ev.title}
                      </h3>
                      <p className={styles.eventDesc}>{ev.description}</p>
                      {ev.document_id && (
                        <span className={styles.sourceLink}>📎 Source document linked</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
