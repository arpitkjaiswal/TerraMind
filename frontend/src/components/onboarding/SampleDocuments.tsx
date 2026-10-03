"use client";
import { useState } from "react";
import { sampleDocuments } from "@/data/sample-documents";
import type { SampleDocument } from "@/data/sample-documents";

interface Props { plotId?: string; busy?: boolean; onImport?: (samples: SampleDocument[]) => Promise<void>; }

export default function SampleDocuments({ plotId, busy = false, onImport }: Props) {
  const [samplePlot, setSamplePlot] = useState(plotId && ["plot-A", "plot-B", "plot-C"].includes(plotId) ? plotId : "plot-B");
  const samples = sampleDocuments.filter(sample => sample.plot_id === samplePlot);
  return <section style={{ padding: 18, border: "1px solid var(--border)", borderRadius: 12, display: "grid", gap: 12 }} aria-label="Synthetic sample documents">
    <h2 style={{ fontSize: 17 }}>Sample document library</h2>
    <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>18 fictional CSV records across three fields. Every row is labeled synthetic. Download originals to inspect them.{onImport ? " Import adds six labeled samples to your selected field using normal document processing." : " These samples are already included in the local demo and its graph."}</p>
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
      <label>Sample pack <select aria-label="Sample document pack" value={samplePlot} disabled={busy} onChange={event => setSamplePlot(event.target.value)}><option value="plot-A">Field A · Wheat</option><option value="plot-B">Field B · Corn</option><option value="plot-C">Field C · Soybean</option></select></label>
      {onImport && <button className="btn btn-secondary" disabled={busy} onClick={() => void onImport(samples)}>Import 6 synthetic documents</button>}
    </div>
    <ul style={{ paddingLeft: 20, display: "grid", gap: 6, fontSize: 12 }}>{samples.map(sample => <li key={sample.id}><a href={`/sample-documents/${sample.filename}`} download>{sample.label}</a></li>)}</ul>
  </section>;
}
