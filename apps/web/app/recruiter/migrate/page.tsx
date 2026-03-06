"use client";

import { useEffect, useRef, useState } from "react";

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
  batchId: string | null;
  batchStatus: BatchStatus | null;
}

interface BatchStatus {
  batch_id: string;
  status: string;
  total_files: number;
  files_completed: number;
  files_succeeded: number;
  files_failed: number;
}

export default function RecruiterMigrationWizard() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
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
    batchId: null,
    batchStatus: null,
  });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // On mount, check for existing in-progress migration jobs
  const resumeChecked = useRef(false);
  useEffect(() => {
    if (resumeChecked.current) return;
    resumeChecked.current = true;

    (async () => {
      try {
        const res = await fetch(`${API}/api/recruiter/migration/history/list`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const jobs = await res.json();
        // Find most recent active job
        const active = jobs.find(
          (j: { status: string }) =>
            j.status === "pending" ||
            j.status === "queued" ||
            j.status === "importing",
        );
        if (!active) return;

        // Fetch full status
        const statusRes = await fetch(
          `${API}/api/recruiter/migration/${active.id}`,
          { credentials: "include" },
        );
        if (!statusRes.ok) return;
        const data = await statusRes.json();

        const batchId = (data.stats?.batch_id as string) || null;
        setMigration((prev) => ({
          ...prev,
          jobId: data.id,
          platform: data.source_platform_detected || data.source_platform,
          confidence: 0,
          evidence: [],
          rowCount: data.stats?.total_files ?? 0,
          status: data.status,
          stats: data.stats,
          errors: data.errors,
          batchId,
        }));

        if (data.status === "pending") {
          setStep("detection");
        } else {
          setStep("progress");
          // Will start polling after state update via the effect below
        }
      } catch {
        // Ignore — user may not be authenticated or no prior jobs
      }
    })();

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Start polling when we enter progress step with a jobId (covers both fresh start and resume)
  useEffect(() => {
    if (step === "progress" && migration.jobId && !pollRef.current) {
      startPolling();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, migration.jobId]);

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

  function uploadFile() {
    if (!file) return;
    setUploading(true);
    setUploadPct(0);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `${API}/api/recruiter/migration/upload?source_platform=auto`,
    );
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setUploadPct(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const data = JSON.parse(xhr.responseText);
        setMigration((prev) => ({
          ...prev,
          jobId: data.job_id,
          platform: data.detected_platform,
          confidence: data.confidence,
          evidence: data.evidence,
          rowCount: data.row_count,
          status: "pending",
        }));
        setStep("detection");
      } else {
        setError(xhr.responseText || `Upload failed (${xhr.status})`);
      }
      setUploading(false);
    };

    xhr.onerror = () => {
      setError("Network error during upload");
      setUploading(false);
    };

    xhr.send(formData);
  }

  async function startImport() {
    if (!migration.jobId) return;
    setStarting(true);
    setError(null);
    try {
      await apiFetch(`/api/recruiter/migration/${migration.jobId}/start`, {
        method: "POST",
      });
      setStep("progress");
    } catch (e: unknown) {
      setError((e as Error).message);
    }
    setStarting(false);
  }

  // Use a ref to read latest migration state without re-creating the interval
  const migrationRef = useRef(migration);
  migrationRef.current = migration;

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const cur = migrationRef.current;
      try {
        if (cur.batchId) {
          // Poll batch endpoint for per-file progress
          const batch = await apiFetch(
            `/api/upload-batches/${cur.batchId}/status`,
          );
          setMigration((p) => ({
            ...p,
            batchStatus: batch,
            status: batch.status === "completed" ? "completed" : p.status,
          }));
          if (batch.status === "completed") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setStep("summary");
          }
        } else {
          // Poll migration endpoint to discover batch_id
          const data = await apiFetch(
            `/api/recruiter/migration/${cur.jobId}`,
          );
          setMigration((p) => ({
            ...p,
            status: data.status,
            stats: data.stats
              ? { ...data.stats, worker_stale: data.worker_stale }
              : data.worker_stale
                ? { worker_stale: true }
                : null,
            errors: data.errors,
            batchId:
              p.batchId || (data.stats?.batch_id as string) || null,
          }));
          if (data.status === "completed" || data.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setStep("summary");
          }
        }
      } catch {
        // Ignore transient polling errors
      }
    }, 2000);
  }

  const [rolling, setRolling] = useState(false);
  async function rollback() {
    if (
      !migration.jobId ||
      !confirm(
        "Are you sure you want to rollback this migration? All imported data will be deleted.",
      )
    )
      return;
    setRolling(true);
    try {
      await apiFetch(`/api/recruiter/migration/${migration.jobId}/rollback`, {
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
        CRM Data Migration
      </h1>
      <p className="mb-8 text-sm text-slate-500">
        Import your clients, jobs, and candidates from Bullhorn, Recruit CRM,
        CATSOne, Zoho Recruit, or any CSV export.
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
                    : ["detection", "progress", "summary"].indexOf(step) >= i
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
          ),
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
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
                : "Drop your CRM export file here, or click to browse"}
            </p>
            <p className="mb-4 text-xs text-slate-400">
              CSV, JSON, ZIP, or XLSX — CRM exports or ZIP archive of PDF/DOCX
              resumes (Agency plan)
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
          {file && !uploading && (
            <button
              onClick={uploadFile}
              className="mt-6 w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Upload & Detect Platform
            </button>
          )}
          {uploading && (
            <div className="mt-6">
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700">
                  {uploadPct < 100 ? "Uploading..." : "Detecting platform..."}
                </span>
                <span className="text-slate-500">{uploadPct}%</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-300 ease-out"
                  style={{ width: `${uploadPct}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Detection */}
      {step === "detection" && (() => {
        const isResume = migration.platform === "resume_archive";
        const estHours = Math.max(1, Math.ceil((migration.rowCount * 1.5) / 3600));
        return (
          <div className="rounded-xl border border-slate-200 bg-white p-8">
            <h2 className="mb-4 text-lg font-semibold text-slate-800">
              {isResume ? "Resume Archive Detected" : "Platform Detected"}
            </h2>
            <div className="mb-6 rounded-lg bg-blue-50 p-4">
              <div className="flex items-center gap-3">
                <div className="text-2xl font-bold capitalize text-blue-700">
                  {isResume ? "Resume Archive" : migration.platform.replace("_", " ")}
                </div>
                <div className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
                  {Math.round(migration.confidence * 100)}% confidence
                </div>
              </div>
              <div className="mt-2 text-sm text-blue-600">
                {isResume
                  ? `${migration.rowCount.toLocaleString()} resume files detected (PDF/DOCX)`
                  : `${migration.rowCount.toLocaleString()} rows detected`}
              </div>
            </div>

            {isResume && (
              <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                Resumes will be parsed in the background. You&apos;ll receive an
                email when processing is complete &mdash; you can safely close
                this page. Estimated time: ~{estHours}{" "}
                {estHours === 1 ? "hour" : "hours"}.
              </div>
            )}

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
              {starting
                ? "Starting import..."
                : isResume
                  ? "Start Resume Import"
                  : "Start Import"}
            </button>
          </div>
        );
      })()}

      {/* Step 3: Progress */}
      {step === "progress" && (() => {
        const stats = migration.stats as Record<string, number> | null;
        const batch = migration.batchStatus;
        const isResume = migration.platform === "resume_archive";
        const workerStale = (migration.stats as Record<string, unknown> | null)?.worker_stale;
        const waitingForWorker = isResume && !batch && !stats;

        // For resume archives with batch tracking, use granular per-file data
        const processed = batch
          ? batch.files_completed
          : isResume
            ? (stats?.processed_files ?? 0)
            : stats
              ? (stats.imported ?? 0) + (stats.merged ?? 0) + (stats.skipped ?? 0) + (stats.errors ?? 0)
              : 0;
        const total = batch
          ? batch.total_files
          : isResume
            ? ((stats?.total_files ?? migration.rowCount) || 1)
            : (migration.rowCount || 1);
        const pct = waitingForWorker ? 0 : Math.min(100, Math.round((processed / total) * 100));
        const unit = isResume ? "files" : "rows";

        return (
          <div className="rounded-xl border border-slate-200 bg-white p-8">
            <h2 className="mb-4 text-lg font-semibold text-slate-800">
              {isResume ? "Resume Parsing in Progress" : "Import in Progress"}
            </h2>

            {isResume && (
              <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">
                Processing continues in the background. You&apos;ll receive an
                email when complete &mdash; feel free to close this page.
              </div>
            )}

            {workerStale ? (
              <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                The background worker appears to be starting up. This can take a
                few minutes on first use. If this persists beyond 10 minutes,
                please contact support.
              </div>
            ) : null}

            {waitingForWorker && !workerStale && (
              <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                Preparing your files for processing. This usually takes a minute
                or two&hellip;
              </div>
            )}

            {/* Progress bar */}
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700">
                {waitingForWorker ? "Starting..." : `${pct}% complete`}
              </span>
              {!waitingForWorker && (
                <span className="text-slate-500">
                  {processed.toLocaleString()} / {total.toLocaleString()} {unit}
                </span>
              )}
            </div>
            <div className="mb-6 h-3 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full transition-all duration-500 ease-out ${
                  waitingForWorker
                    ? "w-full animate-pulse bg-slate-300"
                    : "bg-blue-600"
                }`}
                style={waitingForWorker ? undefined : { width: `${pct}%` }}
              />
            </div>

            <div className="flex items-center gap-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              <span className="text-sm text-slate-600">
                {waitingForWorker
                  ? "Queued for processing..."
                  : `Processing... Status: ${batch?.status || migration.status}`}
              </span>
            </div>

            {batch ? (
              <div className="mt-4 grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-green-50 p-3 text-center">
                  <div className="text-lg font-bold text-green-700">{batch.files_succeeded}</div>
                  <div className="text-xs text-green-600">Succeeded</div>
                </div>
                <div className="rounded-lg bg-red-50 p-3 text-center">
                  <div className="text-lg font-bold text-red-700">{batch.files_failed}</div>
                  <div className="text-xs text-red-600">Failed</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3 text-center">
                  <div className="text-lg font-bold text-slate-700">{batch.total_files - batch.files_completed}</div>
                  <div className="text-xs text-slate-600">Remaining</div>
                </div>
              </div>
            ) : stats && !waitingForWorker ? (
              <div className="mt-4 grid grid-cols-4 gap-3">
                <div className="rounded-lg bg-green-50 p-3 text-center">
                  <div className="text-lg font-bold text-green-700">{stats.imported ?? 0}</div>
                  <div className="text-xs text-green-600">Imported</div>
                </div>
                <div className="rounded-lg bg-blue-50 p-3 text-center">
                  <div className="text-lg font-bold text-blue-700">{stats.merged ?? 0}</div>
                  <div className="text-xs text-blue-600">Merged</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3 text-center">
                  <div className="text-lg font-bold text-slate-700">{stats.skipped ?? 0}</div>
                  <div className="text-xs text-slate-600">Skipped</div>
                </div>
                <div className="rounded-lg bg-red-50 p-3 text-center">
                  <div className="text-lg font-bold text-red-700">{stats.errors ?? 0}</div>
                  <div className="text-xs text-red-600">Errors</div>
                </div>
              </div>
            ) : null}
          </div>
        );
      })()}

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
              {migration.batchStatus ? (
                <div className="mt-2 space-y-1 text-sm text-green-600">
                  <div>Succeeded: {migration.batchStatus.files_succeeded} files</div>
                  <div>Failed: {migration.batchStatus.files_failed} files</div>
                  <div>Total: {migration.batchStatus.total_files} files</div>
                </div>
              ) : migration.stats ? (
                <div className="mt-2 space-y-1 text-sm text-green-600">
                  <div>
                    Imported:{" "}
                    {String(
                      (migration.stats as Record<string, unknown>).imported ?? 0,
                    )}{" "}
                    records
                  </div>
                  <div>
                    Merged (duplicates):{" "}
                    {String(
                      (migration.stats as Record<string, unknown>).merged ?? 0,
                    )}
                  </div>
                  <div>
                    Skipped:{" "}
                    {String(
                      (migration.stats as Record<string, unknown>).skipped ?? 0,
                    )}
                  </div>
                  <div>
                    Errors:{" "}
                    {String(
                      (migration.stats as Record<string, unknown>).errors ?? 0,
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mb-6 rounded-lg bg-red-50 p-4">
              <div className="text-lg font-bold text-red-700">Import failed</div>
              {migration.errors &&
                (migration.errors as unknown[]).length > 0 && (
                  <pre className="mt-2 max-h-40 overflow-auto text-xs text-red-600">
                    {JSON.stringify(migration.errors, null, 2)}
                  </pre>
                )}
            </div>
          )}

          {migration.status === "completed" && migration.platform === "resume_archive" && (
            <a
              href="/recruiter/candidates"
              className="mb-4 block rounded-lg bg-blue-50 p-3 text-center text-sm font-medium text-blue-700 hover:bg-blue-100"
            >
              View imported candidates in pipeline &rarr;
            </a>
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
                  batchId: null,
                  batchStatus: null,
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
