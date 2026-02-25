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

interface FileResult {
  filename: string;
  success: boolean;
  status: string | null;
  pipeline_candidate_id: number | null;
  candidate_profile_id: number | null;
  matched_email: string | null;
  parsed_name: string | null;
  error: string | null;
}

interface UploadResponse {
  results: FileResult[];
  total_submitted: number;
  total_succeeded: number;
  total_failed: number;
  total_matched: number;
  total_new: number;
  total_linked_platform: number;
  remaining_monthly_quota: number;
  upgrade_recommendation: string | null;
}

function isAcceptedFile(file: File): boolean {
  if (ACCEPTED_TYPES.includes(file.type)) return true;
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  return ACCEPTED_EXTENSIONS.includes(ext);
}

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  matched: { bg: "bg-green-50", text: "text-green-700", label: "Matched" },
  new: { bg: "bg-blue-50", text: "text-blue-700", label: "New" },
  linked_platform: { bg: "bg-yellow-50", text: "text-yellow-700", label: "Platform User" },
  failed: { bg: "bg-red-50", text: "text-red-700", label: "Failed" },
};

export default function ResumeUploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [pct, setPct] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Simulated progress that ticks up while waiting for each file to process
  useEffect(() => {
    if (!uploading) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }
    timerRef.current = setInterval(() => {
      setPct((prev) => {
        // Each file owns an equal slice; tick up toward ~95% of current file's ceiling
        const fileSlice = 100 / progress.total;
        const ceiling = (progress.current + 1) * fileSlice - 2;
        if (prev >= ceiling) return prev;
        // Slow down as we approach the ceiling (ease-out feel)
        const remaining = ceiling - prev;
        const step = Math.max(0.3, remaining * 0.04);
        return Math.min(prev + step, ceiling);
      });
    }, 300);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [uploading, progress]);
  const [response, setResponse] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const accepted = Array.from(newFiles).filter(isAcceptedFile);
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      const deduped = accepted.filter((f) => !existing.has(f.name + f.size));
      return [...prev, ...deduped];
    });
    setError(null);
    setResponse(null);
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

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);
    setResponse(null);
    setProgress({ current: 0, total: files.length });
    setPct(0);

    const allResults: FileResult[] = [];
    let totalSucceeded = 0;
    let totalFailed = 0;
    let totalMatched = 0;
    let totalNew = 0;
    let totalLinkedPlatform = 0;
    let remainingQuota = 0;
    let upgradeRec: string | null = null;

    for (let i = 0; i < files.length; i++) {
      setProgress({ current: i, total: files.length });

      const formData = new FormData();
      formData.append("files", files[i]);

      try {
        const res = await fetch(`${API_BASE}/api/recruiter/pipeline/upload-resumes`, {
          method: "POST",
          credentials: "include",
          body: formData,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => null);
          allResults.push({
            filename: files[i].name,
            success: false,
            status: "failed",
            pipeline_candidate_id: null,
            candidate_profile_id: null,
            matched_email: null,
            parsed_name: null,
            error: body?.detail || `Upload failed (${res.status})`,
          });
          totalFailed++;
          setPct(Math.round(((i + 1) / files.length) * 100));
          continue;
        }

        const data: UploadResponse = await res.json();
        allResults.push(...data.results);
        totalSucceeded += data.total_succeeded;
        totalFailed += data.total_failed;
        totalMatched += data.total_matched;
        totalNew += data.total_new;
        totalLinkedPlatform += data.total_linked_platform;
        remainingQuota = data.remaining_monthly_quota;
        if (data.upgrade_recommendation) upgradeRec = data.upgrade_recommendation;
        // Snap progress to completed percentage
        setPct(Math.round(((i + 1) / files.length) * 100));
      } catch {
        allResults.push({
          filename: files[i].name,
          success: false,
          status: "failed",
          pipeline_candidate_id: null,
          candidate_profile_id: null,
          matched_email: null,
          parsed_name: null,
          error: "Network error",
        });
        totalFailed++;
        setPct(Math.round(((i + 1) / files.length) * 100));
      }
    }

    setPct(100);
    setProgress({ current: files.length, total: files.length });
    setResponse({
      results: allResults,
      total_submitted: files.length,
      total_succeeded: totalSucceeded,
      total_failed: totalFailed,
      total_matched: totalMatched,
      total_new: totalNew,
      total_linked_platform: totalLinkedPlatform,
      remaining_monthly_quota: remainingQuota,
      upgrade_recommendation: upgradeRec,
    });
    setFiles([]);
    setUploading(false);
  }

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
            email.
          </p>
        </div>
      </div>

      {/* Drop zone */}
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

      {/* File list */}
      {files.length > 0 && (
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
            {uploading
              ? `Processing ${progress.current + 1} of ${progress.total} — ${Math.round(pct)}%`
              : `Upload ${files.length} Resume${files.length !== 1 ? "s" : ""}`}
          </button>
          {uploading && (
            <div className="w-full rounded-full bg-slate-200 h-2.5 overflow-hidden">
              <div
                className="h-full bg-slate-900 transition-all duration-300 ease-out"
                style={{ width: `${Math.max(2, Math.round(pct))}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {response && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="font-medium text-slate-900">
                {response.total_succeeded}/{response.total_submitted} processed
              </span>
              {response.total_matched > 0 && (
                <span className="rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                  {response.total_matched} matched
                </span>
              )}
              {response.total_new > 0 && (
                <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                  {response.total_new} new
                </span>
              )}
              {response.total_linked_platform > 0 && (
                <span className="rounded-full bg-yellow-50 px-2.5 py-0.5 text-xs font-medium text-yellow-700">
                  {response.total_linked_platform} platform users
                </span>
              )}
              {response.total_failed > 0 && (
                <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                  {response.total_failed} failed
                </span>
              )}
              <span className="ml-auto text-xs text-slate-500">
                {response.remaining_monthly_quota} imports remaining this month
              </span>
            </div>
          </div>

          {response.upgrade_recommendation && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {response.upgrade_recommendation}
            </div>
          )}

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
                {response.results.map((r, i) => {
                  const badge = STATUS_BADGE[r.status || "failed"] || STATUS_BADGE.failed;
                  return (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-sm text-slate-700 max-w-[200px] truncate">
                        {r.filename}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-700">
                        {r.parsed_name || "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {r.matched_email || "-"}
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
                        {r.success && r.candidate_profile_id && (
                          <Link
                            href={`/recruiter/candidates/${r.candidate_profile_id}`}
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
        </div>
      )}
    </div>
  );
}
