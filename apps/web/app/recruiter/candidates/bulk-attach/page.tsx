"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface MatchInfo {
  candidate_id: number;
  matched_by: string;
  confidence: string;
  candidate_name: string;
  candidate_email: string | null;
}

interface FileMatch {
  filename: string;
  file_size: number;
  match_key: { type: string; value: string | number };
  matches: MatchInfo[];
  matched: boolean;
}

interface PreviewData {
  batch_id: string;
  zip_staged_path: string;
  file_matches: FileMatch[];
  total_files: number;
  matched_files: number;
  unmatched_files: number;
}

interface BatchStatus {
  batch_id: string;
  status: string;
  total_files: number;
  files_completed: number;
  files_succeeded: number;
  files_failed: number;
}

type Step = "upload" | "preview" | "processing" | "complete";

export default function BulkAttachPage() {
  const [step, setStep] = useState<Step>("upload");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [processing, setProcessing] = useState(false);
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const uploadZip = useCallback(async (file: File) => {
    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/bulk-attach/preview`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Upload failed" }));
        setError(data.detail || "Upload failed");
        return;
      }

      const data: PreviewData = await res.json();
      setPreview(data);

      // Auto-select all matched files
      const autoSelected = new Set<string>();
      for (const fm of data.file_matches) {
        if (fm.matched && fm.matches.length > 0) {
          autoSelected.add(fm.filename);
        }
      }
      setSelected(autoSelected);
      setStep("preview");
    } catch {
      setError("Failed to upload ZIP file. Please try again.");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) uploadZip(file);
    },
    [uploadZip],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file && file.name.toLowerCase().endsWith(".zip")) {
        uploadZip(file);
      } else {
        setError("Please drop a ZIP file.");
      }
    },
    [uploadZip],
  );

  const toggleFile = (filename: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const handleProcess = async () => {
    if (!preview || selected.size === 0) return;

    setProcessing(true);
    setError(null);

    const selectedMatches = preview.file_matches
      .filter((fm) => selected.has(fm.filename) && fm.matches.length > 0)
      .map((fm) => ({
        filename: fm.filename,
        candidate_id: fm.matches[0].candidate_id,
        matched_by: fm.matches[0].matched_by,
      }));

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/bulk-attach/process`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_id: preview.batch_id,
          zip_staged_path: preview.zip_staged_path,
          selected_matches: selectedMatches,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Processing failed" }));
        setError(data.detail || "Processing failed");
        setProcessing(false);
        return;
      }

      const data = await res.json();
      setStep("processing");

      // Start polling batch status
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(
            `${API_BASE}/api/upload-batches/${data.batch_id}/status`,
            { credentials: "include" },
          );
          if (statusRes.ok) {
            const statusData: BatchStatus = await statusRes.json();
            setBatchStatus(statusData);

            if (statusData.status === "completed" || statusData.status === "failed") {
              if (pollRef.current) clearInterval(pollRef.current);
              setStep("complete");
              setProcessing(false);
            }
          }
        } catch {
          // ignore polling errors
        }
      }, 2000);
    } catch {
      setError("Failed to start processing. Please try again.");
      setProcessing(false);
    }
  };

  const confidenceBadge = (confidence: string) => {
    const colors =
      confidence === "high"
        ? "bg-green-50 text-green-700"
        : "bg-yellow-50 text-yellow-700";
    return (
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors}`}
      >
        {confidence}
      </span>
    );
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Bulk Attach Resumes
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload a ZIP of resumes to match and attach to existing pipeline
            candidates
          </p>
        </div>
        <Link
          href="/recruiter/candidates"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          Back to Candidates
        </Link>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center gap-2 text-sm">
        {(["upload", "preview", "processing", "complete"] as Step[]).map(
          (s, i) => (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && (
                <div className="h-px w-6 bg-slate-300" />
              )}
              <span
                className={`rounded-full px-3 py-1 font-medium ${
                  step === s
                    ? "bg-slate-900 text-white"
                    : (["upload", "preview", "processing", "complete"].indexOf(step) >
                      i
                      ? "bg-slate-200 text-slate-700"
                      : "bg-slate-100 text-slate-400")
                }`}
              >
                {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
              </span>
            </div>
          ),
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Step 1: Upload */}
      {step === "upload" && (
        <div
          className={`rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
            dragOver
              ? "border-slate-900 bg-slate-50"
              : "border-slate-300 bg-white"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {uploading ? (
            <div className="space-y-3">
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
              <p className="text-sm text-slate-600">
                Uploading and analyzing ZIP...
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                <svg
                  className="h-6 w-6 text-slate-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>
              <div>
                <p className="text-base font-medium text-slate-900">
                  Drag and drop a ZIP file here
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  or click to browse
                </p>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
              >
                Select ZIP File
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                onChange={handleFileSelect}
                className="hidden"
              />
              <div className="mt-4 text-xs text-slate-400">
                <p>
                  Name files to match candidates: <strong>email@example.com.pdf</strong>,{" "}
                  <strong>candidate_123.pdf</strong>, or{" "}
                  <strong>John_Smith.pdf</strong>
                </p>
                <p className="mt-1">
                  Supports PDF and DOCX files. Max 500 files, 200 MB total.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Preview matches */}
      {step === "preview" && preview && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-slate-900">
                  {preview.total_files}
                </div>
                <div className="text-xs text-slate-500">Total Files</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {preview.matched_files}
                </div>
                <div className="text-xs text-slate-500">Matched</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-400">
                  {preview.unmatched_files}
                </div>
                <div className="text-xs text-slate-500">Unmatched</div>
              </div>
            </div>
          </div>

          {/* Select/Deselect all matched */}
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={
                  selected.size ===
                  preview.file_matches.filter((f) => f.matched).length
                }
                onChange={() => {
                  const matchedFiles = preview.file_matches
                    .filter((f) => f.matched)
                    .map((f) => f.filename);
                  if (selected.size === matchedFiles.length) {
                    setSelected(new Set());
                  } else {
                    setSelected(new Set(matchedFiles));
                  }
                }}
                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
              />
              Select all matched ({preview.matched_files})
            </label>
            <span className="text-sm text-slate-500">
              {selected.size} selected
            </span>
          </div>

          {/* File list */}
          <div className="space-y-2">
            {preview.file_matches.map((fm) => (
              <div
                key={fm.filename}
                className={`rounded-lg border p-3 ${
                  fm.matched
                    ? "border-slate-200 bg-white"
                    : "border-slate-100 bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-3">
                  {fm.matched && (
                    <input
                      type="checkbox"
                      checked={selected.has(fm.filename)}
                      onChange={() => toggleFile(fm.filename)}
                      className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-slate-900">
                        {fm.filename}
                      </span>
                      <span className="text-xs text-slate-400">
                        {formatSize(fm.file_size)}
                      </span>
                    </div>
                    {fm.matched && fm.matches.length > 0 ? (
                      <div className="mt-1 flex items-center gap-2 text-xs text-slate-600">
                        <span>
                          Matched to{" "}
                          <strong>{fm.matches[0].candidate_name}</strong>
                          {fm.matches[0].candidate_email &&
                            ` (${fm.matches[0].candidate_email})`}
                        </span>
                        <span className="text-slate-300">|</span>
                        <span>via {fm.matches[0].matched_by}</span>
                        {confidenceBadge(fm.matches[0].confidence)}
                      </div>
                    ) : (
                      <div className="mt-1 text-xs text-slate-400">
                        No matching candidate found
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleProcess}
              disabled={selected.size === 0 || processing}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-50"
            >
              {processing
                ? "Processing..."
                : `Attach ${selected.size} Resume${selected.size !== 1 ? "s" : ""}`}
            </button>
            <button
              onClick={() => {
                setStep("upload");
                setPreview(null);
                setSelected(new Set());
                setError(null);
              }}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Start Over
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Processing */}
      {step === "processing" && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
          <h2 className="text-lg font-semibold text-slate-900">
            Processing Resumes...
          </h2>
          {batchStatus && (
            <div className="mt-4 space-y-3">
              <div className="mx-auto max-w-md">
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-slate-900 transition-all duration-500"
                    style={{
                      width: `${batchStatus.total_files > 0 ? (batchStatus.files_completed / batchStatus.total_files) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
              <p className="text-sm text-slate-500">
                {batchStatus.files_completed} of {batchStatus.total_files}{" "}
                files processed
              </p>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Complete */}
      {step === "complete" && batchStatus && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
            <svg
              className="h-6 w-6 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-900">
            Bulk Attach Complete
          </h2>
          <div className="mt-4 grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-slate-900">
                {batchStatus.total_files}
              </div>
              <div className="text-xs text-slate-500">Total</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">
                {batchStatus.files_succeeded}
              </div>
              <div className="text-xs text-slate-500">Attached</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red-500">
                {batchStatus.files_failed}
              </div>
              <div className="text-xs text-slate-500">Failed</div>
            </div>
          </div>
          <div className="mt-6">
            <Link
              href="/recruiter/candidates"
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
            >
              Back to Candidates
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
