"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx"];

interface BatchFileResult {
  filename: string;
  status: string; // pending | processing | succeeded | failed | skipped
  error: string | null;
  result: {
    status?: string;
    pipeline_candidate_id?: number;
    candidate_profile_id?: number;
    matched_email?: string;
    parsed_name?: string;
  } | null;
}

interface BatchStatusResponse {
  batch_id: string;
  status: string; // pending | processing | completed
  total_files: number;
  files_completed: number;
  files_succeeded: number;
  files_failed: number;
  files: BatchFileResult[];
  page: number;
  page_size: number;
  total_pages: number;
}

interface MigrationStatusResponse {
  id: number;
  status: string; // pending | queued | importing | completed | failed
  queue_position?: number;
  estimated_wait_minutes?: number;
  batch_progress?: {
    batch_id: string;
    total_files: number;
    files_completed: number;
    files_succeeded: number;
    files_failed: number;
  };
  stats?: { batch_id?: string };
}

function isAcceptedFile(file: File): boolean {
  if (ACCEPTED_TYPES.includes(file.type)) return true;
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  return ACCEPTED_EXTENSIONS.includes(ext);
}

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  succeeded: { bg: "bg-green-50", text: "text-green-700", label: "Processed" },
  matched: { bg: "bg-green-50", text: "text-green-700", label: "Matched" },
  new: { bg: "bg-blue-50", text: "text-blue-700", label: "New" },
  linked_platform: { bg: "bg-yellow-50", text: "text-yellow-700", label: "Platform User" },
  failed: { bg: "bg-red-50", text: "text-red-700", label: "Failed" },
  pending: { bg: "bg-slate-50", text: "text-slate-500", label: "Pending" },
  processing: { bg: "bg-amber-50", text: "text-amber-700", label: "Processing" },
};

const POLL_INTERVAL = 2000;
const QUEUE_POLL_INTERVAL = 5000;

export default function ResumeUploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [batchStatus, setBatchStatus] = useState<BatchStatusResponse | null>(null);
  const [migrationStatus, setMigrationStatus] = useState<MigrationStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const migrationPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up polls on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (migrationPollRef.current) clearInterval(migrationPollRef.current);
    };
  }, []);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const accepted = Array.from(newFiles).filter(isAcceptedFile);
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      const deduped = accepted.filter((f) => !existing.has(f.name + f.size));
      return [...prev, ...deduped];
    });
    setError(null);
    setBatchStatus(null);
    setMigrationStatus(null);
  }, []);

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  }

  // Poll migration status (for queued/importing states)
  function startMigrationPolling(jobId: number) {
    if (migrationPollRef.current) clearInterval(migrationPollRef.current);
    migrationPollRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/recruiter/migration/${jobId}`,
          { credentials: "include" }
        );
        if (!res.ok) return;
        const data: MigrationStatusResponse = await res.json();
        setMigrationStatus(data);

        if (data.status === "importing" && data.batch_progress) {
          // Switch to batch polling for detailed progress
          if (migrationPollRef.current) clearInterval(migrationPollRef.current);
          migrationPollRef.current = null;
          startProcessingPolling(data.batch_progress.batch_id);
        } else if (data.status === "completed" || data.status === "failed") {
          if (migrationPollRef.current) clearInterval(migrationPollRef.current);
          migrationPollRef.current = null;
          setUploading(false);
          if (data.stats?.batch_id) {
            loadResultsPage(data.stats.batch_id, 1);
          }
        }
      } catch {
        // Keep polling on network errors
      }
    }, QUEUE_POLL_INTERVAL);
  }

  // Poll batch status during processing (summary-only, no file details)
  function startProcessingPolling(batchId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/upload-batches/${batchId}/status?include_files=false`,
          { credentials: "include" }
        );
        if (!res.ok) return;
        const data: BatchStatusResponse = await res.json();
        setBatchStatus(data);
        if (data.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setUploading(false);
          // Fetch first page of results
          loadResultsPage(batchId, 1);
        }
      } catch {
        // Keep polling on network errors
      }
    }, POLL_INTERVAL);
  }

  // Legacy polling for HTTP uploads (non-migration path)
  function startPolling(batchId: string) {
    startProcessingPolling(batchId);
  }

  async function loadResultsPage(batchId: string, page: number) {
    try {
      const res = await fetch(
        `${API_BASE}/api/upload-batches/${batchId}/status?include_files=true&page=${page}&page_size=100`,
        { credentials: "include" }
      );
      if (!res.ok) return;
      const data: BatchStatusResponse = await res.json();
      setBatchStatus(data);
      setCurrentPage(page);
    } catch {
      // Ignore
    }
  }

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);
    setBatchStatus(null);
    setMigrationStatus(null);

    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }

    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/pipeline/upload-resumes`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(body?.detail || `Upload failed (${res.status})`);
        setUploading(false);
        return;
      }

      const data = await res.json();
      const batchId = data.batch_id;

      // Set initial status
      setBatchStatus({
        batch_id: batchId,
        status: "processing",
        total_files: data.total_files,
        files_completed: 0,
        files_succeeded: 0,
        files_failed: 0,
        files: [],
        page: 1,
        page_size: 100,
        total_pages: 1,
      });

      setFiles([]);
      startPolling(batchId);
    } catch {
      setError("Network error. Please try again.");
      setUploading(false);
    }
  }

  const pct = batchStatus && batchStatus.total_files > 0
    ? Math.round((batchStatus.files_completed / batchStatus.total_files) * 100)
    : 0;

  const isComplete = batchStatus?.status === "completed";
  const isQueued = migrationStatus?.status === "queued";
  const isImporting = migrationStatus?.status === "importing" || (batchStatus && !isComplete && !isQueued);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Link href="/recruiter/candidates" className="hover:text-slate-700">
              Candidates
            </Link>
            <span>/</span>
            <span className="text-slate-900">Upload Resumes</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">
            Bulk Resume Upload
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload resume files to parse and link to your pipeline contacts by
            email. Supports up to 10,000 files via ZIP.
          </p>
        </div>
      </div>

      {/* Queued state */}
      {isQueued && migrationStatus && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
            <svg className="h-6 w-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-amber-900">
            Your import is #{migrationStatus.queue_position} in queue
          </h3>
          <p className="mt-1 text-sm text-amber-700">
            Another import is currently running. Yours will start automatically
            when it finishes.
          </p>
          {migrationStatus.estimated_wait_minutes != null && migrationStatus.estimated_wait_minutes > 0 && (
            <p className="mt-2 text-sm font-medium text-amber-800">
              Estimated wait: ~{Math.round(migrationStatus.estimated_wait_minutes)} minutes
            </p>
          )}
          <div className="mt-4">
            <div className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
              Waiting in queue
            </div>
          </div>
        </div>
      )}

      {/* Drop zone */}
      {!uploading && !isComplete && !isQueued && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
            dragActive
              ? "border-slate-500 bg-slate-50"
              : "border-slate-300 hover:border-slate-400 hover:bg-slate-50"
          }`}
        >
          <svg
            className="mx-auto h-10 w-10 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 16V4m0 0l-4 4m4-4l4 4M4 14v4a2 2 0 002 2h12a2 2 0 002-2v-4"
            />
          </svg>
          <p className="mt-3 text-sm font-medium text-slate-700">
            Drop resume files here or click to browse
          </p>
          <p className="mt-1 text-xs text-slate-500">
            PDF, DOC, DOCX up to 10 MB each
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.doc,.docx"
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
        </div>
      )}

      {/* File list (before upload) */}
      {files.length > 0 && !uploading && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-700">
              {files.length} file{files.length !== 1 ? "s" : ""} selected
            </h2>
            <button
              onClick={() => setFiles([])}
              className="text-xs text-slate-500 hover:text-slate-700"
            >
              Clear all
            </button>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
            {files.map((f, i) => (
              <div
                key={f.name + f.size}
                className="flex items-center justify-between px-4 py-2.5"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-mono text-slate-600 uppercase">
                    {f.name.split(".").pop()}
                  </span>
                  <span className="truncate text-sm text-slate-700">
                    {f.name}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {(f.size / 1024).toFixed(0)} KB
                  </span>
                </div>
                <button
                  onClick={() => removeFile(i)}
                  className="ml-3 shrink-0 text-slate-400 hover:text-red-500"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-50"
          >
            Upload {files.length} Resume{files.length !== 1 ? "s" : ""}
          </button>
        </div>
      )}

      {/* Progress bar (during processing) */}
      {batchStatus && !isComplete && !isQueued && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-slate-700">
              Processing {batchStatus.files_completed.toLocaleString()} of{" "}
              {batchStatus.total_files.toLocaleString()} files...
            </span>
            <span className="text-slate-500">{pct}%</span>
          </div>
          <div className="w-full rounded-full bg-slate-200 h-2.5 overflow-hidden">
            <div
              className="h-full bg-slate-900 transition-all duration-500 ease-out"
              style={{ width: `${Math.max(2, pct)}%` }}
            />
          </div>
          {batchStatus.files_succeeded > 0 || batchStatus.files_failed > 0 ? (
            <div className="flex gap-4 text-xs text-slate-500">
              <span>{batchStatus.files_succeeded.toLocaleString()} succeeded</span>
              {batchStatus.files_failed > 0 && (
                <span className="text-red-500">
                  {batchStatus.files_failed.toLocaleString()} failed
                </span>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results (after completion) */}
      {batchStatus && isComplete && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="font-medium text-slate-900">
                {batchStatus.files_succeeded.toLocaleString()}/{batchStatus.total_files.toLocaleString()} processed
              </span>
              {batchStatus.files_failed > 0 && (
                <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                  {batchStatus.files_failed.toLocaleString()} failed
                </span>
              )}
            </div>
          </div>

          {/* Results table */}
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase">
                    File
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase">
                    Name
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase">
                    Email
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-2.5 text-right text-xs font-medium text-slate-500 uppercase">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {batchStatus.files.map((r, i) => {
                  const resultStatus = r.result?.status || r.status;
                  const badge = STATUS_BADGE[resultStatus] || STATUS_BADGE.failed;
                  return (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-sm text-slate-700 max-w-[200px] truncate">
                        {r.filename}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-700">
                        {r.result?.parsed_name || "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {r.result?.matched_email || "-"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}
                        >
                          {badge.label}
                        </span>
                        {r.error && (
                          <p className="mt-0.5 text-xs text-red-500">{r.error}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {r.status === "succeeded" && r.result?.candidate_profile_id && (
                          <Link
                            href={`/recruiter/candidates/${r.result.candidate_profile_id}`}
                            className="text-xs font-medium text-slate-600 hover:text-slate-900"
                          >
                            View
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination controls */}
          {batchStatus.total_pages > 1 && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">
                Page {currentPage} of {batchStatus.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => loadResultsPage(batchStatus.batch_id, currentPage - 1)}
                  disabled={currentPage <= 1}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => loadResultsPage(batchStatus.batch_id, currentPage + 1)}
                  disabled={currentPage >= batchStatus.total_pages}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          <button
            onClick={() => { setBatchStatus(null); setMigrationStatus(null); setError(null); setCurrentPage(1); }}
            className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            Upload More
          </button>
        </div>
      )}
    </div>
  );
}
