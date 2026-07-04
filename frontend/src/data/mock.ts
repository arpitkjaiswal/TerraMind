import type {
  Farm, Document, QueryResult, TimelineEvent,
  IngestionQueueItem, DashboardStats, GraphNode, GraphEdge
} from "@/types";

export const mockFarm: Farm = {
  id: "farm-001",
  name: "Sunridge Agricultural Holdings",
  owner_user_id: "user-001",
  created_at: "2023-03-15T09:00:00Z",
  plots: [
    { id: "plot-A", farm_id: "farm-001", name: "Field A — North Pasture", crop_type: "Winter Wheat", size_ha: 42.5, created_at: "2023-03-15T09:00:00Z" },
    { id: "plot-B", farm_id: "farm-001", name: "Field B — South Valley", crop_type: "Corn (Hybrid DKC 64-69)", size_ha: 38.2, created_at: "2023-03-15T09:00:00Z" },
    { id: "plot-C", farm_id: "farm-001", name: "Field C — East Ridge", crop_type: "Soybean", size_ha: 29.1, created_at: "2023-03-15T09:00:00Z" },
  ]
};

export const mockDocuments: Document[] = [
  { id: "doc-001", plot_id: "plot-B", source_type: "pdf", label: "Pesticide Application Log — Chlorpyrifos X (Apr 2024)", storage_uri: "/docs/pest-2024.pdf", ingest_status: "ready", source_confidence: 0.98, uploaded_at: "2024-04-12T10:30:00Z", date_of_event: "2024-04-10" },
  { id: "doc-002", plot_id: "plot-B", source_type: "photo", label: "Handwritten note — Cover crop seed mix (Mar 2025)", storage_uri: "/docs/note-2025.jpg", ingest_status: "ready", source_confidence: 0.91, uploaded_at: "2025-03-22T14:15:00Z", date_of_event: "2025-03-20" },
  { id: "doc-003", plot_id: "plot-B", source_type: "csv", label: "Weather Station Export — Drought Index (Jun–Aug 2026)", storage_uri: "/docs/weather-2026.csv", ingest_status: "ready", source_confidence: 1.0, uploaded_at: "2026-09-01T08:00:00Z", date_of_event: "2026-06-01" },
  { id: "doc-004", plot_id: "plot-B", source_type: "csv", label: "Yield Measurement — Harvest 2026 (DKC 64-69)", storage_uri: "/docs/yield-2026.csv", ingest_status: "ready", source_confidence: 1.0, uploaded_at: "2026-10-05T16:00:00Z", date_of_event: "2026-10-03" },
  { id: "doc-005", plot_id: "plot-A", source_type: "photo", label: "Field inspection note — Soil pH reading (Nov 2025)", storage_uri: "/docs/soil-2025.jpg", ingest_status: "review_needed", source_confidence: 0.72, uploaded_at: "2025-11-18T11:00:00Z", date_of_event: "2025-11-15" },
  { id: "doc-006", plot_id: "plot-A", source_type: "pdf", label: "Fertilizer Purchase Receipt — NPK 20-10-10 (Feb 2026)", storage_uri: "/docs/fert-2026.pdf", ingest_status: "ready", source_confidence: 0.95, uploaded_at: "2026-02-28T09:30:00Z", date_of_event: "2026-02-25" },
  { id: "doc-007", plot_id: "plot-C", source_type: "csv", label: "Soybean Yield History 2021–2025", storage_uri: "/docs/soy-hist.csv", ingest_status: "ready", source_confidence: 1.0, uploaded_at: "2026-01-10T13:00:00Z", date_of_event: "2025-10-20" },
];

export const mockDemoQuery: QueryResult = {
  id: "q-001",
  query_text: "Why did Field B's yield drop by 20% in 2026?",
  answer_text: `Field B's 2026 corn harvest (DKC 64-69) recorded **6.8 t/ha**, down from a 3-year average of **8.5 t/ha** — a 20% shortfall. The knowledge graph surfaces a **3-hop causal chain** rooted in documented events:\n\n**1. Chlorpyrifos-X application (April 2024):** Organophosphate pesticides in this class are documented to suppress *Pseudomonas* and *Bacillus* soil microbiome populations for 18–36 months post-application. This effect is confirmed by peer-reviewed literature and is traceable directly to your pesticide log.\n\n**2. Cover crop establishment (March 2025):** The hairy vetch/rye blend was planted in a microbiome-depleted soil state, limiting its nitrogen-fixation efficacy. The connection between docs 001 and 002 is a *statistical association* — the graph detected co-occurrence across 6 linked records, but no mechanism confirmation exists yet.\n\n**3. Severe drought index (June–August 2026):** PDSI values reached −3.8, the worst on record for this plot. Drought stress was amplified by degraded soil structure — a consequence of reduced microbial binding activity from point 1.\n\n**Combined effect:** The compounding sequence — pesticide-driven microbiome suppression → reduced cover crop efficacy → drought-amplified stress — accounts for the modelled 18–22% yield shortfall. The graph cannot confirm a single root cause; the **most evidence-supported interpretation** assigns roughly equal weight to chemical and climatic factors.\n\n**Recommendation scope:** This system explains what happened, not what to apply next. Consider engaging an agronomist to review the evidence trail below before altering next season's inputs.`,
  confidence_label: "statistical_association",
  confidence_score: 0.74,
  evidence_trail: [
    { id: "e-001", graph_node_id: "n-chem-001", node_label: "Chlorpyrifos-X Application", node_type: "ChemicalProduct", relationship_type: "APPLIED_TO", source_document_id: "doc-001", source_document_label: "Pesticide Application Log — Apr 2024", date: "2024-04-10" },
    { id: "e-002", graph_node_id: "n-prac-001", node_label: "Hairy Vetch / Rye Cover Crop", node_type: "Practice", relationship_type: "CORRELATED_WITH", source_document_id: "doc-002", source_document_label: "Handwritten note — Mar 2025", date: "2025-03-20" },
    { id: "e-003", graph_node_id: "n-wx-001", node_label: "Severe Drought (PDSI −3.8)", node_type: "WeatherEvent", relationship_type: "OCCURRED_DURING", source_document_id: "doc-003", source_document_label: "Weather Station Export — Jun–Aug 2026", date: "2026-06-01" },
    { id: "e-004", graph_node_id: "n-yield-001", node_label: "Corn Yield 6.8 t/ha (2026)", node_type: "YieldMeasurement", relationship_type: "CORRELATED_WITH", source_document_id: "doc-004", source_document_label: "Yield Measurement — Oct 2026", date: "2026-10-03" },
  ],
  graph_hops: 3,
  latency_ms: 1840,
  created_at: "2026-10-10T14:22:00Z",
};

export const mockTimeline: TimelineEvent[] = [
  { id: "t-001", date: "2023-03-15", title: "Field B registered", category: "crop", description: "Plot created; DKC 64-69 hybrid corn selected as primary variety.", plot_id: "plot-B", confidence: 1.0 },
  { id: "t-002", date: "2023-10-20", title: "Baseline yield measured", category: "yield", description: "Corn yield 8.6 t/ha — above 3-year district average of 7.9 t/ha.", plot_id: "plot-B", confidence: 1.0 },
  { id: "t-003", date: "2024-04-10", title: "Chlorpyrifos-X applied", category: "chemical", description: "Organophosphate pesticide applied at 1.2 L/ha for aphid control. Application log digitised from receipt.", document_id: "doc-001", plot_id: "plot-B", confidence: 0.98 },
  { id: "t-004", date: "2024-10-18", title: "Yield measured", category: "yield", description: "Corn yield 8.3 t/ha — slight decline, within normal variance. No flag raised.", plot_id: "plot-B", confidence: 1.0 },
  { id: "t-005", date: "2025-03-20", title: "Cover crop planted", category: "practice", description: "Hairy vetch / rye mix sown for nitrogen fixation and erosion control.", document_id: "doc-002", plot_id: "plot-B", confidence: 0.91 },
  { id: "t-006", date: "2025-10-22", title: "Yield measured", category: "yield", description: "Corn yield 8.4 t/ha — stable. Cover crop benefit not yet measurable.", plot_id: "plot-B", confidence: 1.0 },
  { id: "t-007", date: "2026-06-01", title: "Severe drought onset", category: "weather", description: "PDSI reached −3.8 by end of July. Irrigation capacity insufficient to compensate.", document_id: "doc-003", plot_id: "plot-B", confidence: 1.0 },
  { id: "t-008", date: "2026-10-03", title: "Yield drop detected — 20%", category: "yield", description: "Corn yield 6.8 t/ha vs 8.5 t/ha 3-year average. Query triggered.", document_id: "doc-004", plot_id: "plot-B", confidence: 1.0 },
];

export const mockQueue: IngestionQueueItem[] = [
  { id: "q-001", document_id: "doc-005", label: "Field inspection note — Soil pH reading (Nov 2025)", source_type: "photo", confidence: 0.72, extracted_text: "Soil pH at 3 sample points: NW corner 6.1, centre 5.8, SE corner 6.4. Recommend lime application in low-pH zone. Signed: J. Hartley", uploaded_at: "2025-11-18T11:00:00Z", status: "pending" },
  { id: "q-002", document_id: "doc-008", label: "Handwritten irrigation log — Summer 2026", source_type: "photo", confidence: 0.68, extracted_text: "Irrigation dates: Jun 12, Jun 28, Jul 9, Jul 24. Volume approx 30mm each. Pump failure Aug 3 - no further irrigation.", uploaded_at: "2026-09-15T10:30:00Z", status: "pending" },
];

export const mockStats: DashboardStats = {
  total_documents: 7,
  total_queries: 14,
  avg_confidence: 0.76,
  pending_review: 2,
  graph_nodes: 43,
  graph_edges: 87,
};

export const mockGraphNodes: GraphNode[] = [
  { id: "n-field-B", type: "Field", label: "Field B", properties: { size_ha: 38.2, crop_type: "Corn" } },
  { id: "n-chem-001", type: "ChemicalProduct", label: "Chlorpyrifos-X", date: "2024-04-10", properties: { dose: "1.2 L/ha", purpose: "Aphid control" } },
  { id: "n-prac-001", type: "Practice", label: "Cover Crop (Vetch/Rye)", date: "2025-03-20", properties: { species: "Hairy vetch / rye" } },
  { id: "n-wx-001", type: "WeatherEvent", label: "Drought 2026 (PDSI −3.8)", date: "2026-06-01", properties: { pdsi: -3.8, duration_days: 91 } },
  { id: "n-yield-001", type: "YieldMeasurement", label: "Yield 6.8 t/ha (2026)", date: "2026-10-03", properties: { value_tha: 6.8, avg_3yr: 8.5, delta_pct: -20 } },
  { id: "n-crop-001", type: "CropVariant", label: "DKC 64-69 Hybrid", properties: { drought_rating: "moderate" } },
];

export const mockGraphEdges: GraphEdge[] = [
  { id: "e-g-001", source: "n-chem-001", target: "n-field-B", type: "APPLIED_TO", date: "2024-04-10", source_document_id: "doc-001", confirmed: true },
  { id: "e-g-002", source: "n-prac-001", target: "n-field-B", type: "APPLIED_TO", date: "2025-03-20", source_document_id: "doc-002", confirmed: true },
  { id: "e-g-003", source: "n-wx-001", target: "n-field-B", type: "OCCURRED_DURING", date: "2026-06-01", source_document_id: "doc-003", confirmed: true },
  { id: "e-g-004", source: "n-chem-001", target: "n-yield-001", type: "CORRELATED_WITH", source_document_id: "doc-001", confirmed: false },
  { id: "e-g-005", source: "n-wx-001", target: "n-yield-001", type: "CORRELATED_WITH", source_document_id: "doc-003", confirmed: false },
  { id: "e-g-006", source: "n-prac-001", target: "n-yield-001", type: "CORRELATED_WITH", source_document_id: "doc-002", confirmed: false },
  { id: "e-g-007", source: "n-crop-001", target: "n-field-B", type: "APPLIED_TO", confirmed: true },
];

export const suggestedQueries = [
  "Why did Field B's yield drop by 20% in 2026?",
  "What chemicals were applied to Field A in the last 3 seasons?",
  "Which weather events correlate with yield changes across all plots?",
  "Show me the complete treatment history for Field B since 2023.",
  "Are there any documented interactions between pesticide use and soil pH on Field C?",
  "What cover crop practices have correlated with above-average yields?",
];
