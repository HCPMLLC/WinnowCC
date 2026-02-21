"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Step = "upload" | "detection" | "progress" | "summary";

interface MigrationState {
  jobId: number | null;
  platform: string;
  confidence: number;
  evidence: string[];
  rowCount: number;
  status: string;
  stats: Record<string, unknown> | null;
  errors: unknown[] | null;
}

export default function MigrationWizard() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [migration, setMigration] = useState<MigrationState>({
    jobId: null,
    platform: "",
    confidence: 0,
    evidence: [],
    rowCount: 0,
    status: "",
    stats: null,
    errors: null,
  });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function apiFetch(path: string, options: RequestInit = {}) {
    const res = await fetch(`${API}${path}`, {
      credentials: "include",
      ...options,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`${res.status}: ${body}`);
    }
    return res.json();
  }

  // Step 1: Upload
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    const allowedExts = [".csv", ".json", ".zip", ".xlsx"];
    if (f && allowedExts.some((ext) => f.name.toLowerCase().endsWith(ext))) {
      setFile(f);
      setError(null);
    } else {
      setError("Supported formats: CSV, JSON, ZIP, XLSX");
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      setError(null);
    }
  }

  async function uploadFile() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API}/api/migration/upload?source_platform=auto`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body);
      }
      const data = await res.json();
      setMigration({
        ...migration,
        jobId: data.job_id,
        platform: data.detected_platform,
        confidence: data.confidence,
        evidence: data.evidence,
        rowCount: data.row_count,
        status: "pending",
      });
      setStep("detection");
    } catch (e: unknown) {
      setError((e as Error).message);
    }
    setUploading(false);
  }

  // Step 2: Start import
  async function startImport() {
    if (!migration.jobId) return;
    setStarting(true);
    setError(null);
    try {
      await apiFetch(`/api/migration/${migration.jobId}/start`, {
        method: "POST",
      });
      setStep("progress");
      startPolling();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
    setStarting(false);
  }

  // Step 3: Poll for progress
  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await apiFetch(`/api/migration/${migration.jobId}`);
        setMigration((prev) => ({
          ...prev,
          status: data.status,
          stats: data.stats,
          errors: data.errors,
        }));
        if (data.status === "completed" || data.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          setStep("summary");
        }
      } catch {
        // Ignore transient polling errors
      }
    }, 2000);
  }

  // Rollback
  const [rolling, setRolling] = useState(false);
  async function rollback() {
    if (!migration.jobId || !confirm("Are you sure you want to rollback this migration? All imported data will be deleted.")) return;
    setRolling(true);
    try {
      await apiFetch(`/api/migration/${migration.jobId}/rollback`, {
        method: "POST",
      });
      setMigration((prev) => ({ ...prev, status: "rolled_back" }));
    } catch (e: unknown) {
      setError((e as Error).message);
    }
    setRolling(false);
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-slate-900">
        Data Migration
      </h1>
      <p className="mb-8 text-sm text-slate-500">
        Import your data from Bullhorn, Recruit CRM, CATSOne, Zoho Recruit, or
        any CSV export.
      </p>

      {/* Step indicator */}
      <div className="mb-8 flex items-center gap-2">
        {(["upload", "detection", "progress", "summary"] as Step[]).map(
          (s, i) => (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && (
                <div
                  className={`h-px w-8 ${
                    step === s ||
                    ["detection", "progress", "summary"].indexOf(step) >= i
                      ? "bg-blue-400"
                      : "bg-slate-200"
                  }`}
                />
              )}
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                  step === s
                    ? "bg-blue-600 text-white"
                    : ["detection", "progress", "summary"].indexOf(step) >=
                        i
                      ? "bg-blue-100 text-blue-700"
                      : "bg-slate-100 text-slate-400"
                }`}
              >
                {i + 1}
              </div>
              <span
                className={`text-xs font-medium ${
                  step === s ? "text-blue-700" : "text-slate-400"
                }`}
              >
                {s === "upload"
                  ? "Upload"
                  : s === "detection"
                    ? "Detect"
                    : s === "progress"
                      ? "Import"
                      : "Summary"}
              </span>
            </div>
          )
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Step 1: Upload */}
      {step === "upload" && (
        <div className="rounded-xl border border-slate-200 bg-white p-8">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
              dragOver
                ? "border-blue-400 bg-blue-50"
                : "border-slate-200 bg-slate-50"
            }`}
          >
            <svg
              className="mb-4 h-12 w-12 text-slate-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <p className="mb-2 text-sm font-medium text-slate-600">
              {file
                ? file.name
                : "Drop your export file here, or click to browse"}
            </p>
            <p className="mb-4 text-xs text-slate-400">
              CSV, JSON, ZIP, or XLSX from Bullhorn, Recruit CRM, CATSOne, Zoho
              Recruit
            </p>
            <input
              type="file"
              accept=".csv,.json,.zip,.xlsx"
              onChange={handleFileSelect}
              className="hidden"
              id="file-input"
            />
            <label
              htmlFor="file-input"
              className="cursor-pointer rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200"
            >
              Browse files
            </label>
          </div>
          {file && (
            <button
              onClick={uploadFile}
              disabled={uploading}
              className="mt-6 w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? "Uploading & detecting..." : "Upload & Detect Platform"}
            </button>
          )}
        </div>
      )}

      {/* Step 2: Detection / Preview */}
      {step === "detection" && (
        <div className="rounded-xl border border-slate-200 bg-white p-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Platform Detected
          </h2>
          <div className="mb-6 rounded-lg bg-blue-50 p-4">
            <div className="flex items-center gap-3">
              <div className="text-2xl font-bold capitalize text-blue-700">
                {migration.platform.replace("_", " ")}
              </div>
              <div className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
                {Math.round(migration.confidence * 100)}% confidence
              </div>
            </div>
            <div className="mt-2 text-sm text-blue-600">
              {migration.rowCount.toLocaleString()} rows detected
            </div>
          </div>

          {migration.evidence.length > 0 && (
            <div className="mb-6">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Detection Evidence
              </h3>
              <ul className="space-y-1">
                {migration.evidence.map((e, i) => (
                  <li key={i} className="text-sm text-slate-600">
                    &bull; {e}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={startImport}
            disabled={starting}
            className="w-full rounded-lg bg-green-600 px-4 py-3 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
          >
            {starting ? "Starting import..." : "Start Import"}
          </button>
        </div>
      )}

      {/* Step 3: Progress */}
      {step === "progress" && (
        <div className="rounded-xl border border-slate-200 bg-white p-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Import in Progress
          </h2>
          <div className="flex items-center gap-3">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            <span className="text-sm text-slate-600">
              Processing... Status: {migration.status}
            </span>
          </div>
          {migration.stats && (
            <div className="mt-4 rounded-lg bg-slate-50 p-4 text-sm">
              <div>
                Imported: {String((migration.stats as Record<string, unknown>).imported ?? 0)}
              </div>
              <div>
                Skipped: {String((migration.stats as Record<string, unknown>).skipped ?? 0)}
              </div>
              <div>
                Errors: {String((migration.stats as Record<string, unknown>).errors ?? 0)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Summary */}
      {step === "summary" && (
        <div className="rounded-xl border border-slate-200 bg-white p-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Migration {migration.status === "completed" ? "Complete" : "Failed"}
          </h2>

          {migration.status === "completed" ? (
            <div className="mb-6 rounded-lg bg-green-50 p-4">
              <div className="text-lg font-bold text-green-700">
                Successfully imported
              </div>
              {migration.stats && (
                <div className="mt-2 space-y-1 text-sm text-green-600">
                  <div>
                    Imported: {String((migration.stats as Record<string, unknown>).imported ?? 0)} records
                  </div>
                  <div>
                    Skipped (duplicates): {String((migration.stats as Record<string, unknown>).skipped ?? 0)}
                  </div>
                  <div>
                    Errors: {String((migration.stats as Record<string, unknown>).errors ?? 0)}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="mb-6 rounded-lg bg-red-50 p-4">
              <div className="text-lg font-bold text-red-700">
                Import failed
              </div>
              {migration.errors && (migration.errors as unknown[]).length > 0 && (
                <pre className="mt-2 max-h-40 overflow-auto text-xs text-red-600">
                  {JSON.stringify(migration.errors, null, 2)}
                </pre>
              )}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => {
                setStep("upload");
                setFile(null);
                setMigration({
                  jobId: null,
                  platform: "",
                  confidence: 0,
                  evidence: [],
                  rowCount: 0,
                  status: "",
                  stats: null,
                  errors: null,
                });
              }}
              className="flex-1 rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
            >
              New Migration
            </button>
            {migration.status === "completed" && (
              <button
                onClick={rollback}
                disabled={rolling || migration.status === "rolled_back"}
                className="rounded-lg bg-red-100 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-200 disabled:opacity-50"
              >
                {rolling
                  ? "Rolling back..."
                  : migration.status === "rolled_back"
                    ? "Rolled back"
                    : "Rollback"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
