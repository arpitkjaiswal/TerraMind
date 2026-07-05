export type ConfidenceLabel = "documented_fact" | "statistical_association" | "unconfirmed_hypothesis";

export type NodeType = "Field" | "ChemicalProduct" | "WeatherEvent" | "CropVariant" | "YieldMeasurement" | "Practice";
export type EdgeType = "APPLIED_TO" | "OCCURRED_DURING" | "PRECEDED" | "CORRELATED_WITH" | "CONFIRMED_CAUSE";

export interface Plot {
  id: string;
  name: string;
  farm_id: string;
  geo_boundary?: string;
  crop_type: string;
  size_ha: number;
  created_at: string;
}

export interface Farm {
  id: string;
  name: string;
  owner_user_id: string;
  plots: Plot[];
  created_at: string;
}

export interface Document {
  id: string;
  plot_id: string;
  source_type: "pdf" | "photo" | "csv";
  label: string;
  storage_uri: string;
  ingest_status: "processing" | "ready" | "review_needed" | "ingest_failed";
  source_confidence?: number;
  uploaded_at: string;
  date_of_event?: string;
}

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  date?: string;
  properties: Record<string, string | number | boolean>;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  date?: string;
  source_document_id?: string;
  confirmed: boolean;
}

export interface EvidenceEdge {
  id: string;
  graph_node_id: string;
  node_label: string;
  node_type: NodeType;
  relationship_type: EdgeType;
  source_document_id: string;
  source_document_label: string;
  date: string;
}

export interface QueryResult {
  id: string;
  query_text: string;
  answer_text: string;
  confidence_label: ConfidenceLabel;
  confidence_score: number;
  evidence_trail: EvidenceEdge[];
  graph_hops: number;
  latency_ms: number;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  date: string;
  title: string;
  category: "chemical" | "weather" | "crop" | "yield" | "practice";
  description: string;
  document_id?: string;
  confidence?: number;
  plot_id: string;
}

export interface IngestionQueueItem {
  id: string;
  document_id: string;
  label: string;
  source_type: "pdf" | "photo" | "csv";
  confidence: number;
  extracted_text: string;
  uploaded_at: string;
  status: "pending" | "approved" | "rejected";
}

export interface DashboardStats {
  total_documents: number;
  total_queries: number;
  avg_confidence: number;
  pending_review: number;
  graph_nodes: number;
  graph_edges: number;
}
