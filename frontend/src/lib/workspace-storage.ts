import type { Document, IngestionQueueItem, TimelineEvent } from "../types/index";

export type WorkspaceData = { documents: Document[]; timeline: TimelineEvent[]; queue: IngestionQueueItem[]; totalQueries: number };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0;
const date = (value: unknown): value is string => text(value) && /^\d{4}-\d{2}-\d{2}/.test(value) && Number.isFinite(Date.parse(value));
const confidence = (value: unknown) => value === undefined || (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1);
function documents(value: unknown): value is Document[] {
  return Array.isArray(value) && value.every(doc => object(doc) && text(doc.id) && text(doc.plot_id) && text(doc.label)
    && ["pdf", "photo", "csv"].includes(String(doc.source_type)) && typeof doc.storage_uri === "string"
    && ["pending_ocr", "pending_review", "processing", "ready", "review_needed", "ingest_failed"].includes(String(doc.ingest_status))
    && date(doc.uploaded_at) && (doc.date_of_event === undefined || date(doc.date_of_event)) && confidence(doc.source_confidence)
    && (doc.extracted_text === undefined || (typeof doc.extracted_text === "string" && doc.extracted_text.length <= 128_000)))
    && new Set(value.map(doc => doc.id)).size === value.length;
}

/** Stored data is untrusted input: a malformed snapshot must never crash the UI. */
export function restoreWorkspace(raw: string | null, defaults: WorkspaceData, samples: Document[]): WorkspaceData {
  if (!raw) return defaults;
  try {
    const data: unknown = JSON.parse(raw);
    if (!object(data) || !documents(data.documents) || !Array.isArray(data.timeline) || !Array.isArray(data.queue)) return defaults;
    if (!data.timeline.every(event => object(event) && text(event.id) && text(event.plot_id) && date(event.date)
      && text(event.title) && typeof event.description === "string" && confidence(event.confidence)
      && ["chemical", "weather", "crop", "yield", "practice"].includes(String(event.category)))) return defaults;
    if (!data.queue.every(item => object(item) && text(item.id) && text(item.document_id) && text(item.label)
      && typeof item.extracted_text === "string" && date(item.uploaded_at) && confidence(item.confidence)
      && ["photo", "pdf", "csv"].includes(String(item.source_type)) && ["pending", "approved", "rejected"].includes(String(item.status)))) return defaults;
    if (typeof data.totalQueries !== "number" || !Number.isSafeInteger(data.totalQueries) || data.totalQueries < 0) return defaults;
    const restoredDocuments = data.documents;
    return {
      documents: [...restoredDocuments, ...samples.filter(sample => !restoredDocuments.some(doc => doc.id === sample.id))],
      timeline: data.timeline as TimelineEvent[], queue: data.queue as IngestionQueueItem[], totalQueries: data.totalQueries,
    };
  } catch { return defaults; }
}
