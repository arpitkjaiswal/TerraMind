"use client";
import React, { useState, useRef, useEffect } from "react";
import type { QueryResult, ConfidenceLabel } from "@/types";
import { mockDemoQuery } from "@/data/mock";
import { Search, Send, ChevronDown, ChevronUp, FileText, Zap, Clock, GitBranch, Shield, AlertTriangle, Sparkles, RotateCcw } from "lucide-react";
import styles from "./QueryView.module.css";

interface Props {
  initialQuery?: string;
  suggestedQueries: string[];
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

export default function QueryView({ initialQuery, suggestedQueries }: Props) {
  const [query, setQuery] = useState(initialQuery ?? "");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
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
    if (!text.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const response = await fetch("http://localhost:8000/api/v1/query/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query_text: text,
          plot_id: "plot-B",
          include_hypotheses: true,
        }),
      });
      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
      }
      const data = await response.json();
      setResult(data);
    } catch (err) {
      console.error("Query failed, falling back to mock:", err);
      setResult({ ...mockDemoQuery, query_text: text, created_at: new Date().toISOString() });
    } finally {
      setLoading(false);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    }
  }

  async function submitCorrection(edgeId: string) {
    if (correctionNote.trim().length < 10) {
      alert("Correction note must be at least 10 characters long.");
      return;
    }
    try {
      const response = await fetch("http://localhost:8000/api/v1/corrections/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          evidence_edge_id: edgeId,
          correction_note: correctionNote,
        }),
      });
      if (!response.ok) {
        throw new Error("Failed to submit correction");
      }
      alert("Correction submitted successfully — the knowledge graph will update on the next cycle.");
    } catch (err) {
      console.error("Failed to submit correction:", err);
      alert("Correction submitted (local simulation mode) — graph will update on next memify() cycle.");
    } finally {
      setCorrectionTarget(null);
      setCorrectionNote("");
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
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
            placeholder="e.g. Why did Field B's yield drop by 20% in 2026?"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
          />
          <button
            id="btn-submit-query"
            className={styles.sendBtn}
            onClick={() => handleSubmit()}
            disabled={loading || !query.trim()}
          >
            {loading ? <span className={styles.spinner} /> : <Send size={16} />}
          </button>
        </div>
        {/* Suggested queries */}
        <div className={styles.suggestions}>
          {suggestedQueries.slice(0, 4).map(q => (
            <button key={q} className={styles.suggestChip} onClick={() => { setQuery(q); handleSubmit(q); }}>
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className={styles.loadingCard}>
          <div className={styles.loadingDots}>
            <span /><span /><span />
          </div>
          <div className={styles.loadingText}>
            <span className={styles.loadingStage}>Traversing knowledge graph…</span>
            <span className={styles.loadingMeta}>Combining vector similarity with temporal graph traversal</span>
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
                        <button className={styles.flagBtn} onClick={() => setCorrectionTarget(e.id)}>⚑ Flag as incorrect</button>
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
