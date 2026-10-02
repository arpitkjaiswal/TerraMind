"use client";
import React, { useState, useRef, useCallback, useEffect } from "react";
import Image from "next/image";
import type { IngestionQueueItem, Document, Plot, TimelineEvent } from "@/types";
import styles from "./CaptureView.module.css";
import { Upload, FileText, CheckCircle, XCircle, Clock, AlertTriangle, Camera, FilePlus, X, SwitchCamera } from "lucide-react";

interface Props {
  plot: Plot;
  queue: IngestionQueueItem[];
  documents: Document[];
  onQueueChange: (queue: IngestionQueueItem[]) => void;
  onDocumentAdd: (document: Document) => void;
  onDocumentUpdate: (document: Document) => void;
  onTimelineAdd: (event: TimelineEvent) => void;
}

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // 20 MB
const ACCEPTED_TYPES = ".pdf,.csv,.jpg,.jpeg,.png,.tiff,.webp";

export default function CaptureView({ plot, queue, documents, onQueueChange, onDocumentAdd, onDocumentUpdate, onTimelineAdd }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string } | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"user" | "environment">("environment");
  const [capturedPreview, setCapturedPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const cameraRequestRef = useRef(0);

  // ── Camera lifecycle ─────────────────────────────────────────────────────

  const stopCamera = useCallback(() => {
    cameraRequestRef.current += 1;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraReady(false);
    setCapturedPreview(null);
  }, []);

  const startCamera = useCallback(async (facing: "user" | "environment") => {
    const requestId = ++cameraRequestRef.current;
    setCameraError(null);
    setCameraReady(false);
    setCapturedPreview(null);

    // Stop any existing stream first
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      if (requestId !== cameraRequestRef.current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play();
          setCameraReady(true);
        };
      }
    } catch (err: unknown) {
      if (requestId !== cameraRequestRef.current) return;
      const name = err instanceof DOMException ? err.name : "";
      const message = err instanceof Error ? err.message : String(err);
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setCameraError("Camera permission denied. Please allow camera access in your browser settings and try again.");
      } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        setCameraError("No camera found on this device.");
      } else {
        setCameraError(`Camera error: ${message}`);
      }
    }
  }, []);

  function openCamera() { setCameraOpen(true); }

  function closeCamera() {
    stopCamera();
    setCameraOpen(false);
    setCameraError(null);
  }

  function switchCamera() {
    const newFacing = facingMode === "environment" ? "user" : "environment";
    setFacingMode(newFacing);
  }

  function capturePhoto() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Mirror if front camera
    if (facingMode === "user") {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    stopCamera();
    setCapturedPreview(dataUrl);
  }

  async function acceptCapture() {
    if (!capturedPreview) return;

    // Convert data URL → File
    const res = await fetch(capturedPreview);
    const blob = await res.blob();
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const file = new File([blob], `field-capture-${timestamp}.jpg`, { type: "image/jpeg" });

    closeCamera();
    await processFile(file);
  }

  function retakePhoto() { setCapturedPreview(null); }

  // Cleanup camera on unmount
  useEffect(() => {
    return () => { stopCamera(); };
  }, [stopCamera]);

  useEffect(() => {
    if (!cameraOpen || capturedPreview) return;
    const timer = window.setTimeout(() => { void startCamera(facingMode); }, 0);
    return () => window.clearTimeout(timer);
  }, [cameraOpen, capturedPreview, facingMode, startCamera]);

  function approve(id: string) {
    const item = queue.find(entry => entry.id === id);
    if (!item) return;
    onQueueChange(queue.map(entry => entry.id === id ? { ...entry, status: "approved" } : entry));
    const document = documents.find(entry => entry.id === item.document_id);
    if (document) onDocumentUpdate({ ...document, ingest_status: "ready" });
    onTimelineAdd({ id: `review-${item.document_id}`, date: item.uploaded_at.slice(0, 10), title: "Document approved", category: "practice", description: `${item.label} was approved in the local demo review queue.`, document_id: item.document_id, plot_id: plot.id, confidence: item.confidence });
  }
  function reject(id: string) {
    const item = queue.find(entry => entry.id === id);
    if (!item) return;
    onQueueChange(queue.map(entry => entry.id === id ? { ...entry, status: "rejected" } : entry));
    const document = documents.find(entry => entry.id === item.document_id);
    if (document) onDocumentUpdate({ ...document, ingest_status: "ingest_failed" });
  }

  async function processFile(file: File) {
    // Validate file size
    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadResult({ success: false, message: `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 20 MB.` });
      setTimeout(() => setUploadResult(null), 4000);
      return;
    }

    // Validate file type
    const ext = file.name.toLowerCase().split(".").pop() || "";
    const validExts = ["pdf", "csv", "jpg", "jpeg", "png", "tiff", "webp"];
    if (!validExts.includes(ext)) {
      setUploadResult({ success: false, message: `Unsupported file type: .${ext}. Use PDF, CSV, JPG, or PNG.` });
      setTimeout(() => setUploadResult(null), 4000);
      return;
    }

    setUploading(true);
    setUploadResult(null);

    // Local demo processing is deterministic; it does not claim to run an OCR service.
    await new Promise(r => setTimeout(r, 700));

    // Simulate a confidence score based on file type
    const isImage = ["jpg", "jpeg", "png", "tiff", "webp"].includes(ext);
    const simulatedConfidence = isImage ? 0.72 : 0.96;

    const highConf = simulatedConfidence >= 0.85;

    const now = new Date();
    const uploadedAt = now.toISOString();
    const documentId = `doc-local-${now.getTime()}`;
    const doc: Document = {
      id: documentId, plot_id: plot.id, source_type: isImage ? "photo" : ext === "pdf" ? "pdf" : "csv",
      label: file.name, storage_uri: "local-demo://browser", ingest_status: highConf ? "ready" : "review_needed",
      source_confidence: simulatedConfidence, uploaded_at: uploadedAt, date_of_event: uploadedAt.slice(0, 10),
    };
    onDocumentAdd(doc);
    if (highConf) {
      onTimelineAdd({ id: `upload-event-${now.getTime()}`, date: uploadedAt.slice(0, 10), title: "Demo document added", category: "practice", description: `${file.name} was added to the local sample records.`, document_id: documentId, plot_id: plot.id, confidence: simulatedConfidence });
      setUploadResult({
        success: true,
        message: `"${file.name}" added to this browser's demo records (${Math.round(simulatedConfidence * 100)}% demo confidence).`,
      });
    } else {
      // Add to review queue
      const newItem: IngestionQueueItem = {
        id: `upload-${now.getTime()}`,
        document_id: documentId,
        label: file.name,
        source_type: isImage ? "photo" : ext === "pdf" ? "pdf" : "csv",
        confidence: simulatedConfidence,
        extracted_text: `No text was extracted from ${file.name}. This local demo queues image files for a review decision only.`,
        uploaded_at: uploadedAt,
        status: "pending",
      };
      onQueueChange([newItem, ...queue]);
      setUploadResult({
        success: true,
        message: `"${file.name}" added to this browser's review queue (${Math.round(simulatedConfidence * 100)}% demo confidence).`,
      });
    }

    setUploading(false);
    setTimeout(() => setUploadResult(null), 5000);
  }

  async function handleFileDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      await processFile(files[0]);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
    // Reset so the same file can be selected again
    e.target.value = "";
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  const pending = queue.filter(i => i.status === "pending");
  const resolved = queue.filter(i => i.status !== "pending");

  return (
    <div className={styles.container}>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        style={{ display: "none" }}
        onChange={handleFileSelect}
      />

      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Ingest & Review — Demo</h1>
          <p className={styles.subtitle}>Demo mode: files stay on this device. OCR is simulated and review decisions persist in this browser.</p>
        </div>
      </div>

      {/* Upload zone */}
      <div
        className={`${styles.dropZone} ${dragOver ? styles.dropZoneActive : ""} ${uploading ? styles.dropZoneUploading : ""}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleFileDrop}
        onClick={openFilePicker}
      >
        {uploading ? (
          <div className={styles.uploadingState}>
            <div className={styles.uploadSpinner} />
            <span>Preparing local demo record…</span>
          </div>
        ) : uploadResult ? (
          <div className={styles.uploadDone}>
            {uploadResult.success ? (
              <CheckCircle size={28} color="var(--green-400)" />
            ) : (
              <XCircle size={28} color="#f87171" />
            )}
            <span>{uploadResult.message}</span>
          </div>
        ) : (
          <>
            <div className={styles.dropIcon}>
              <Upload size={28} color="var(--text-muted)" />
            </div>
            <div className={styles.dropText}>
              <span className={styles.dropTitle}>Drop field notes, receipts, or weather PDFs</span>
              <span className={styles.dropSub}>PDF, CSV, JPG, PNG · Max 20 MB</span>
            </div>
            <div className={styles.dropBtns}>
              <button className="btn btn-secondary" id="btn-upload-file" onClick={(e) => { e.stopPropagation(); openFilePicker(); }}><FilePlus size={14} />Browse files</button>
              <button className="btn btn-secondary" id="btn-capture-photo" onClick={(e) => { e.stopPropagation(); openCamera(); }}><Camera size={14} />Capture photo</button>
            </div>
            <div className={styles.dropRule}>
              <span className={styles.ruleBox} style={{ background: "rgba(34,197,94,0.08)", borderColor: "rgba(34,197,94,0.2)", color: "var(--green-400)" }}>
                PDF and CSV → Added directly in this demo
              </span>
              <span className={styles.ruleBox} style={{ background: "rgba(245,158,11,0.08)", borderColor: "rgba(245,158,11,0.2)", color: "var(--amber-400)" }}>
                Images → Manual review queue in this demo
              </span>
            </div>
          </>
        )}
      </div>

      {/* Review queue */}
      {pending.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <AlertTriangle size={15} color="var(--amber-400)" />
            <h2 className={styles.sectionTitle}>Awaiting Review ({pending.length})</h2>
          </div>
          <div className={styles.queueList}>
            {pending.map(item => (
              <div key={item.id} className={styles.queueCard}>
                <div className={styles.queueTop}>
                  <div className={styles.queueIconWrap}>
                    <FileText size={14} color="var(--amber-400)" />
                  </div>
                  <div className={styles.queueInfo}>
                    <span className={styles.queueLabel}>{item.label}</span>
                    <div className={styles.queueMeta}>
                      <span>{item.source_type.toUpperCase()}</span>
                      <span>·</span>
                      <span>Demo score: <strong style={{ color: item.confidence >= 0.7 ? "var(--amber-400)" : "#f87171" }}>{Math.round(item.confidence * 100)}%</strong></span>
                      <span>·</span>
                      <span>{item.uploaded_at.slice(0, 10)}</span>
                    </div>
                  </div>
                  <div className={styles.queueActions}>
                    <button className={styles.approveBtn} id={`btn-approve-${item.id}`} onClick={() => approve(item.id)}>
                      <CheckCircle size={13} />Approve
                    </button>
                    <button className={styles.rejectBtn} id={`btn-reject-${item.id}`} onClick={() => reject(item.id)}>
                      <XCircle size={13} />Reject
                    </button>
                  </div>
                </div>
                <div className={styles.extractedText}>
                  <div className={styles.extractedLabel}>Review note:</div>
                  <div className={styles.extractedContent}>{item.extracted_text}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Resolved */}
      {resolved.length > 0 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle} style={{ fontSize: 14 }}>Recently resolved</h2>
          {resolved.map(item => (
            <div key={item.id} className={`${styles.resolvedRow} ${item.status === "approved" ? styles.resolvedApproved : styles.resolvedRejected}`}>
              {item.status === "approved" ? <CheckCircle size={13} color="var(--green-400)" /> : <XCircle size={13} color="#f87171" />}
              <span>{item.label}</span>
              <span className={styles.resolvedStatus}>{item.status}</span>
            </div>
          ))}
        </div>
      )}

      {/* Indexed documents */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>All Documents ({documents.length})</h2>
        <div className={styles.docGrid}>
          {documents.map(doc => (
            <div key={doc.id} className={styles.docCard}>
              <div className={styles.docCardTop}>
                <span className={`${styles.docType} ${doc.source_type === "photo" ? styles.docTypePhoto : doc.source_type === "csv" ? styles.docTypeCsv : styles.docTypePdf}`}>
                  {doc.source_type.toUpperCase()}
                </span>
                {doc.ingest_status === "ready" ? (
                  <span className={styles.statusTag} style={{ color: "var(--green-400)" }}><CheckCircle size={10} />Indexed</span>
                ) : doc.ingest_status === "review_needed" ? (
                  <span className={styles.statusTag} style={{ color: "var(--amber-400)" }}><Clock size={10} />Review</span>
                ) : doc.ingest_status === "ingest_failed" ? (
                  <span className={styles.statusTag} style={{ color: "#f87171" }}><XCircle size={10} />Rejected</span>
                ) : (
                  <span className={styles.statusTag} style={{ color: "var(--text-muted)" }}>Processing</span>
                )}
              </div>
              <div className={styles.docCardLabel}>{doc.label}</div>
              <div className={styles.docCardMeta}>
                {doc.date_of_event ?? doc.uploaded_at.slice(0, 10)}
                {doc.source_confidence != null && ` · ${Math.round(doc.source_confidence * 100)}% conf`}
              </div>
            </div>
          ))}
        </div>
      </div>
      {/* ── Camera Modal ──────────────────────────────────────────────── */}
      {cameraOpen && (
        <div className={styles.cameraOverlay} onClick={closeCamera}>
          <div className={styles.cameraModal} onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className={styles.cameraHeader}>
              <div className={styles.cameraHeaderLeft}>
                <Camera size={16} />
                <span>Capture Field Document</span>
              </div>
              <button className={styles.cameraCloseBtn} onClick={closeCamera}>
                <X size={18} />
              </button>
            </div>

            {/* Viewfinder */}
            <div className={styles.cameraViewfinder}>
              {cameraError ? (
                <div className={styles.cameraErrorState}>
                  <XCircle size={36} color="#f87171" />
                  <p>{cameraError}</p>
                  <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={() => startCamera(facingMode)}>
                    Try again
                  </button>
                </div>
              ) : capturedPreview ? (
                <Image
                  src={capturedPreview}
                  alt="Captured photo"
                  className={styles.cameraPreviewImg}
                  fill
                  sizes="(max-width: 600px) 100vw, 640px"
                  unoptimized
                />
              ) : (
                <>
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className={`${styles.cameraVideo} ${facingMode === "user" ? styles.cameraVideoMirrored : ""}`}
                  />
                  {!cameraReady && (
                    <div className={styles.cameraLoading}>
                      <div className={styles.uploadSpinner} />
                      <span>Starting camera…</span>
                    </div>
                  )}
                  {/* Corner brackets for viewfinder feel */}
                  <div className={`${styles.cornerBracket} ${styles.cornerTL}`} />
                  <div className={`${styles.cornerBracket} ${styles.cornerTR}`} />
                  <div className={`${styles.cornerBracket} ${styles.cornerBL}`} />
                  <div className={`${styles.cornerBracket} ${styles.cornerBR}`} />
                </>
              )}
            </div>

            {/* Controls */}
            <div className={styles.cameraControls}>
              {capturedPreview ? (
                <>
                  <button className={styles.cameraRetakeBtn} onClick={retakePhoto}>
                    Retake
                  </button>
                  <button className={styles.cameraAcceptBtn} onClick={acceptCapture}>
                    <CheckCircle size={16} />
                    Use Photo
                  </button>
                </>
              ) : (
                <>
                  <button className={styles.cameraSwitchBtn} onClick={switchCamera} title="Switch camera">
                    <SwitchCamera size={18} />
                  </button>
                  <button
                    className={styles.cameraShutterBtn}
                    onClick={capturePhoto}
                    disabled={!cameraReady}
                    title="Take photo"
                  >
                    <div className={styles.shutterInner} />
                  </button>
                  <div style={{ width: 44 }} /> {/* Spacer to center shutter */}
                </>
              )}
            </div>

            <p className={styles.cameraTip}>
              Keep the document centered and well lit. Photo capture is saved only as a local demo record.
            </p>
          </div>

          {/* Hidden canvas for snapshot */}
          <canvas ref={canvasRef} style={{ display: "none" }} />
        </div>
      )}
    </div>
  );
}
