"use client";
import React, { useState, useRef, useEffect } from "react";
import type { QueryResult, ConfidenceLabel, Document, EvidenceEdge, NodeType } from "@/types";
import { Search, Send, ChevronDown, ChevronUp, FileText, Zap, Clock, GitBranch, Shield, AlertTriangle, Sparkles, RotateCcw } from "lucide-react";
import styles from "./QueryView.module.css";

interface Props {
  initialQuery?: string;
  plotName: string;
  documents: Document[];
  suggestedQueries: string[];
  onQueryComplete: () => void;
}

const CONF_META: Record<ConfidenceLabel, { label: string; cls: string; desc: string; icon: typeof Shield }> = {
  documented_fact:       { label: "Documented Fact",       cls: "badge-fact",  desc: "Directly stated in a source document", icon: Shield },
  statistical_association: { label: "Statistical Association", cls: "badge-assoc", desc: "Co-occurrence across multiple linked records — mechanism unconfirmed", icon: AlertTriangle },
  unconfirmed_hypothesis: { label: "Unconfirmed Hypothesis", cls: "badge-hypo",  desc: "Plausible but weakly supported — shown on explicit request only", icon: Zap },
};

const NODE_TYPE_COLOR: Record<string, string> = {
  ChemicalProduct: "var(--amber-400)",
  WeatherEvent: "var(--sky-400)",
  CropVariant: "var(--green-400)",
  YieldMeasurement: "#f87171",
  Practice: "#fb923c",
  Field: "var(--green-300)",
};

function parseMarkdownBold(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**")
      ? <strong key={i}>{p.slice(2, -2)}</strong>
      : p
  );
}

function AnswerBlock({ text }: { text: string }) {
  const paragraphs = text.split("\n\n");
  return (
    <div className={styles.answerBlock}>
      {paragraphs.map((para, i) => (
        <p key={i} className={styles.answerPara}>
          {parseMarkdownBold(para)}
        </p>
      ))}
    </div>
  );
}

export default function QueryView({ initialQuery, suggestedQueries, plotName, documents, onQueryComplete }: Props) {
  const [query, setQuery] = useState(initialQuery ?? "");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [trailOpen, setTrailOpen] = useState(true);
  const [correctionTarget, setCorrectionTarget] = useState<string | null>(null);
  const [correctionNote, setCorrectionNote] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (initialQuery) {
      handleSubmit(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  async function handleSubmit(q?: string) {
    const text = q ?? query;
    if (text.trim().length < 5 || text.length > 2000) {
      setError("Enter a question between 5 and 2,000 characters.");
      return;
    }
    setError(null);
    setIsDemo(true);
    setLoading(true);
    setResult(null);
    await new Promise(resolve => setTimeout(resolve, 300));
    const name = plotName.split(" — ")[0];
    const evidence: EvidenceEdge[] = documents.map(doc => {
      const label = doc.label.toLowerCase();
      const nodeType: NodeType = label.includes("weather") || label.includes("drought") ? "WeatherEvent" : label.includes("yield") ? "YieldMeasurement" : label.includes("pesticide") || label.includes("fertilizer") || label.includes("chemical") ? "ChemicalProduct" : label.includes("crop") ? "CropVariant" : "Practice";
      return { id: `demo-evidence-${doc.id}`, graph_node_id: `demo-${doc.id}`, node_label: doc.label, node_type: nodeType, relationship_type: "APPLIED_TO", source_document_id: doc.id, source_document_label: doc.label, date: doc.date_of_event ?? doc.uploaded_at.slice(0, 10) };
    });
    const answer = documents.length
      ? `This local demo has ${documents.length} sample record${documents.length === 1 ? "" : "s"} for ${name}. The record titles and dates below are available as evidence, but this demo does not read file contents or establish causes.\n\n${documents.map(doc => `**${doc.date_of_event ?? doc.uploaded_at.slice(0, 10)} — ${doc.label}**`).join("\n\n")}\n\nTreat this as an index of records, not an agronomic conclusion. Connect a configured backend and document processing service for answers based on extracted content.`
      : `There are no sample documents indexed for ${name} yet. Add a file in Ingest & Review to see it appear here. This local demo does not infer causes from missing records.`;
    setResult({ id: `demo-query-${Date.now()}`, query_text: text, answer_text: answer, confidence_label: "documented_fact", confidence_score: documents.length ? 0.6 : 0.2, evidence_trail: evidence, graph_hops: 0, latency_ms: 300, created_at: new Date().toISOString() });
    onQueryComplete();
    setLoading(false);
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
  }

  async function submitCorrection(edgeId: string) {
    if (correctionNote.trim().length < 10) {
      alert("Correction note must be at least 10 characters long.");
      return;
    }
    setError("Corrections need a configured backend and reviewer account. No correction was saved in this local demo.");
    setCorrectionTarget(edgeId);
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey && !loading) { e.preventDefault(); handleSubmit(); }
  }

  const cm = result ? CONF_META[result.confidence_label] : null;
  const ConfIcon = cm?.icon ?? Shield;

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerIcon}><Sparkles size={20} /></div>
        <div>
          <h1 className={styles.title}>Ask Aegis</h1>
          <p className={styles.subtitle}>Plain-language questions answered with a transparent evidence trail from your field records.</p>
        </div>
      </div>

      {/* Query input */}
      <div className={styles.inputCard}>
        <div className={styles.inputRow}>
          <Search size={16} color="var(--text-muted)" className={styles.inputIcon} />
          <textarea
            ref={inputRef}
            id="query-input"
            className={styles.textarea}
          placeholder={`Ask about the sample records for ${plotName.split(" — ")[0]}…`}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
          />
          <button
            id="btn-submit-query"
            className={styles.sendBtn}
            onClick={() => handleSubmit()}
            disabled={loading || query.trim().length < 5 || query.length > 2000}
          >
            {loading ? <span className={styles.spinner} /> : <Send size={16} />}
          </button>
        </div>
        {/* Suggested queries */}
        <div className={styles.suggestions}>
          {suggestedQueries.slice(0, 4).map(suggestion => {
            const q = suggestion.replace(/Field [ABC]/g, plotName.split(" — ")[0]);
            return (
            <button key={q} className={styles.suggestChip} disabled={loading} onClick={() => { setQuery(q); handleSubmit(q); }}>
              {q}
            </button>
            );
          })}
        </div>
      </div>

      {error && <p role="alert">{error}</p>}
      <p role="status">Local demo query for {plotName.split(" — ")[0]}: answers use record titles and dates; no AI service is connected.</p>
      {isDemo && <p role="status">Demo answer generated for this question from this field&apos;s local records.</p>}

      {/* Loading state */}
      {loading && (
        <div className={styles.loadingCard}>
          <div className={styles.loadingDots}>
            <span /><span /><span />
          </div>
          <div className={styles.loadingText}>
            <span className={styles.loadingStage}>Preparing local demo answer…</span>
            <span className={styles.loadingMeta}>Using the selected field&apos;s sample record index</span>
          </div>
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <div ref={resultsRef} className={`${styles.resultCard} animate-fade-in`}>
          {/* Result header */}
          <div className={styles.resultHeader}>
            <div className={styles.resultMeta}>
              <span className={`badge ${cm!.cls}`}>
                <ConfIcon size={10} />
                {cm!.label}
              </span>
              <span className={styles.metaItem}><GitBranch size={12} />{result.graph_hops} hops</span>
              <span className={styles.metaItem}><Clock size={12} />{result.latency_ms}ms</span>
              <span className={styles.metaItem}><Zap size={12} />{Math.round(result.confidence_score * 100)}% confidence</span>
            </div>
            <button className={styles.resetBtn} onClick={() => { setResult(null); setQuery(""); }}><RotateCcw size={14} />New query</button>
          </div>

          <div className={styles.queryEcho}>&ldquo;{result.query_text}&rdquo;</div>

          {/* Answer */}
          <AnswerBlock text={result.answer_text} />

          {/* Confidence explanation */}
          <div className={styles.confBox}>
            <ConfIcon size={14} />
            <span><strong>{cm!.label}:</strong> {cm!.desc}.</span>
          </div>

          {/* Evidence trail */}
          <div className={styles.trailSection}>
            <button className={styles.trailToggle} onClick={() => setTrailOpen(o => !o)}>
              <FileText size={14} />
              <span>Evidence Trail — {result.evidence_trail.length} source links</span>
              {trailOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {trailOpen && (
              <div className={styles.trailList}>
                {result.evidence_trail.map((e, idx) => (
                  <div key={e.id} className={styles.trailItem}>
                    <div className={styles.trailStep}>{idx + 1}</div>
                    <div className={styles.trailContent}>
                      <div className={styles.trailNodeRow}>
                        <span
                          className={styles.trailNodeType}
                          style={{ background: `${NODE_TYPE_COLOR[e.node_type] ?? "#888"}18`, color: NODE_TYPE_COLOR[e.node_type] ?? "#888", border: `1px solid ${NODE_TYPE_COLOR[e.node_type] ?? "#888"}35` }}
                        >
                          {e.node_type}
                        </span>
                        <span className={styles.trailNodeLabel}>{e.node_label}</span>
                      </div>
                      <div className={styles.trailDoc}>
                        <FileText size={11} />
                        <span>{e.source_document_label}</span>
                        <span className={styles.trailDate}>{e.date}</span>
                        <span className={styles.trailRel}>{e.relationship_type.replace(/_/g, " ")}</span>
                      </div>
                      {/* Correction */}
                      {correctionTarget === e.id ? (
                        <div className={styles.correctionBox}>
                          <textarea
                            className={styles.correctionInput}
                            placeholder="Describe the correction (e.g. 'This pesticide was applied to Field A, not B')"
                            value={correctionNote}
                            onChange={x => setCorrectionNote(x.target.value)}
                            rows={2}
                          />
                          <div className={styles.correctionBtns}>
                            <button className="btn btn-primary" style={{ fontSize: 12, padding: "6px 14px" }} onClick={() => submitCorrection(e.id)}>Submit</button>
                            <button className="btn btn-ghost" style={{ fontSize: 12, padding: "6px 14px" }} onClick={() => setCorrectionTarget(null)}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <button className={styles.flagBtn} disabled={isDemo} onClick={() => setCorrectionTarget(e.id)}>⚑ Flag as incorrect</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Scope guardrail */}
          <div className={styles.guardrail}>
            <Shield size={13} />
            <span>Aegis explains what happened — it does not recommend chemical applications or dosages. Consult a licensed agronomist before changing inputs.</span>
          </div>
        </div>
      )}
    </div>
  );
}
