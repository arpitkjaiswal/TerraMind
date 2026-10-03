import type { Document, GraphNode, GraphEdge, Plot } from "../types/index";
import type { SampleDocument } from "../data/sample-documents";

export function buildDemoGraph(plot: Plot, documents: Document[], samples: SampleDocument[], seed: { nodes: GraphNode[]; edges: GraphEdge[] } = { nodes: [], edges: [] }) {
  const field = seed.nodes.find(node => node.type === "Field") ?? {
    id: `field-${plot.id}`, type: "Field" as const, label: plot.name,
    properties: { crop_type: plot.crop_type, size_ha: plot.size_ha },
  };
  const nodes: GraphNode[] = seed.nodes.length ? [...seed.nodes] : [field];
  const edges: GraphEdge[] = [...seed.edges];
  for (const doc of documents.filter(document => document.plot_id === plot.id)) {
    const id = `document-${doc.id}`;
    const date = doc.date_of_event ?? doc.uploaded_at.slice(0, 10);
    nodes.push({ id, type: "Document", label: doc.label, date, properties: { source: doc.source_type, status: doc.ingest_status, source_document_id: doc.id } });
    edges.push({ id: `record-${doc.id}`, source: field.id, target: id, type: "HAS_DOCUMENT", date, source_document_id: doc.id, confirmed: true });
    const sample = samples.find(sample => sample.id === doc.id && sample.plot_id === plot.id);
    if (sample && doc.ingest_status === "ready") {
      nodes.push({ id: `entity-${doc.id}`, type: sample.type, label: sample.entity_label, date: sample.date, properties: sample.properties });
      edges.push({ id: `evidence-${doc.id}`, source: id, target: `entity-${doc.id}`, type: "DOCUMENTS", date: sample.date, source_document_id: doc.id, confirmed: true });
    }
  }
  return { nodes, edges };
}
