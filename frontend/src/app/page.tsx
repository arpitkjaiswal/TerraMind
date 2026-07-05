"use client";
import React, { useState } from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import DashboardView from "@/components/dashboard/DashboardView";
import QueryView from "@/components/query/QueryView";
import TimelineView from "@/components/timeline/TimelineView";
import GraphView from "@/components/graph/GraphView";
import CaptureView from "@/components/onboarding/CaptureView";
import {
  mockFarm, mockDocuments, mockStats, mockTimeline,
  mockQueue, mockGraphNodes, mockGraphEdges, suggestedQueries
} from "@/data/mock";
import type { Plot } from "@/types";
import styles from "./page.module.css";

type Section = "dashboard" | "query" | "timeline" | "graph" | "capture";

export default function Home() {
  const [section, setSection] = useState<Section>("dashboard");
  const [activePlot, setActivePlot] = useState<Plot>(mockFarm.plots[1]); // Field B
  const [pendingQuery, setPendingQuery] = useState<string | undefined>();

  function navigateToQuery(q: string) {
    setPendingQuery(q);
    setSection("query");
  }

  function handleSectionChange(s: string) {
    setSection(s as Section);
    if (s !== "query") setPendingQuery(undefined);
  }

  const plotDocs = mockDocuments.filter(d => d.plot_id === activePlot.id);
  const plotTimeline = mockTimeline.filter(e => e.plot_id === activePlot.id);

  return (
    <div className={styles.layout}>
      <Sidebar
        farm={mockFarm}
        activePlot={activePlot}
        onPlotChange={p => { setActivePlot(p); setSection("dashboard"); }}
        activeSection={section}
        onSectionChange={handleSectionChange}
      />
      <main className={styles.main}>
        {section === "dashboard" && (
          <DashboardView
            stats={mockStats}
            plot={activePlot}
            documents={plotDocs}
            onAskQuery={navigateToQuery}
          />
        )}
        {section === "query" && (
          <QueryView
            key={pendingQuery}
            initialQuery={pendingQuery}
            suggestedQueries={suggestedQueries}
          />
        )}
        {section === "timeline" && (
          <TimelineView events={plotTimeline} plot={activePlot} />
        )}
        {section === "graph" && (
          <GraphView nodes={mockGraphNodes} edges={mockGraphEdges} />
        )}
        {section === "capture" && (
          <CaptureView queue={mockQueue} documents={mockDocuments} />
        )}
      </main>
    </div>
  );
}
