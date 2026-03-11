"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { parseApiError } from "../../lib/api-error";
import { useProgress } from "../../hooks/useProgress";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface RecruiterJob {
  id: number;
  title: string;
  status: string;
  client_company_name: string | null;
  client_id: number | null;
  client_name: string | null;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  hourly_rate_min: number | null;
  hourly_rate_max: number | null;
  priority: string | null;
  positions_to_fill: number;
  positions_filled: number;
  department: string | null;
  job_id_external: string | null;
  matched_candidates_count: number;
  created_at: string;
  posted_at: string | null;
  start_at: string | null;
  closes_at: string | null;
}

interface ClientOption {
  id: number;
  company_name: string;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800",
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  closed: "bg-red-100 text-red-800",
};

export default function RecruiterJobsPage() {
  const [jobs, setJobs] = useState<RecruiterJob[]>([]);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [statusFilter, setStatusFilter] = useState("active");
  const [sortBy, setSortBy] = useState("closes_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadBatchStatus, setUploadBatchStatus] = useState<{
    batch_id: string;
    status: string;
    total_files: number;
    files_completed: number;
    files_succeeded: number;
    files_failed: number;
    files: { filename: string; status: string; error: string | null; result: { title?: string; job_id?: number } | null }[];
  } | null>(null);
  const uploadPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkAction, setBulkAction] = useState<"idle" | "deleting" | "updating" | "refreshing">("idle");
  const [bulkStatus, setBulkStatus] = useState("active");
  const [refreshBanner, setRefreshBanner] = useState("");
  const syncProgress = useProgress();

  // Form state
  const [form, setForm] = useState({
    title: "",
    description: "",
    requirements: "",
    nice_to_haves: "",
    location: "",
    remote_policy: "",
    employment_type: "",
    salary_min: "",
    salary_max: "",
    client_company_name: "",
    client_id: "",
    priority: "normal",
    positions_to_fill: "1",
    department: "",
    application_url: "",
    start_at: "",
    closes_at: "",
    job_id_external: "",
    status: "active",
  });

  async function fetchJobs() {
    try {
      const url = new URL(`${API_BASE}/api/recruiter/jobs`);
      if (statusFilter) url.searchParams.set("status", statusFilter);
      if (sortBy) url.searchParams.set("sort_by", sortBy);
      if (sortDir) url.searchParams.set("sort_dir", sortDir);
      if (debouncedSearch) url.searchParams.set("search", debouncedSearch);
      const res = await fetch(url.toString(), { credentials: "include" });
      if (res.ok) {
        setJobs(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    }
  }

  // Debounce search input
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      fetchJobs(),
      fetch(`${API_BASE}/api/recruiter/clients`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : []))
        .then((data) => setClients(data))
        .catch(() => {}),
    ]).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, sortBy, sortDir, debouncedSearch]);

  // Cleanup upload polling on unmount
  useEffect(() => {
    return () => { if (uploadPollRef.current) clearInterval(uploadPollRef.current); };
  }, []);

  const allSelected = jobs.length > 0 && jobs.every((j) => selected.has(j.id));

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(jobs.map((j) => j.id)));
    }
  }

  function chunkArray<T>(arr: T[], size: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < arr.length; i += size) {
      chunks.push(arr.slice(i, i + size));
    }
    return chunks;
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} job${selected.size !== 1 ? "s" : ""}? This cannot be undone.`)) return;

    setBulkAction("deleting");
    try {
      const batches = chunkArray([...selected], 100);
      for (const batch of batches) {
        const params = new URLSearchParams();
        for (const id of batch) params.append("ids", String(id));
        const res = await fetch(`${API_BASE}/api/recruiter/jobs/bulk-delete?${params.toString()}`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(parseApiError(data, "Failed to delete jobs"));
          break;
        }
      }
      setSelected(new Set());
      fetchJobs();
    } catch {
      setError("Network error");
    } finally {
      setBulkAction("idle");
    }
  }

  async function handleBulkStatusUpdate() {
    if (selected.size === 0) return;

    setBulkAction("updating");
    try {
      const batches = chunkArray([...selected], 100);
      for (const batch of batches) {
        const params = new URLSearchParams();
        for (const id of batch) params.append("ids", String(id));
        params.append("new_status", bulkStatus);
        const res = await fetch(`${API_BASE}/api/recruiter/jobs/bulk-status?${params.toString()}`, {
          method: "PATCH",
          credentials: "include",
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(parseApiError(data, "Failed to update jobs"));
          break;
        }
      }
      setSelected(new Set());
      fetchJobs();
    } catch {
      setError("Network error");
    } finally {
      setBulkAction("idle");
    }
  }

  async function handleBulkRefresh() {
    if (selected.size === 0) return;

    setBulkAction("refreshing");
    try {
      const batches = chunkArray([...selected], 100);
      for (const batch of batches) {
        const params = new URLSearchParams();
        for (const id of batch) params.append("ids", String(id));
        const res = await fetch(`${API_BASE}/api/recruiter/jobs/bulk-refresh?${params.toString()}`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(parseApiError(data, "Failed to refresh candidates"));
          return;
        }
      }
      setRefreshBanner(`Candidate refresh is processing in the background for ${selected.size} job${selected.size !== 1 ? "s" : ""}.`);
      setSelected(new Set());
    } catch {
      setError("Network error");
    } finally {
      setBulkAction("idle");
    }
  }

  async function handleCreateJob(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError("");

    const body: Record<string, unknown> = {
      title: form.title,
      description: form.description,
      status: form.status,
    };
    if (form.requirements) body.requirements = form.requirements;
    if (form.nice_to_haves) body.nice_to_haves = form.nice_to_haves;
    if (form.location) body.location = form.location;
    if (form.remote_policy) body.remote_policy = form.remote_policy;
    if (form.employment_type) body.employment_type = form.employment_type;
    if (form.salary_min) body.salary_min = parseInt(form.salary_min);
    if (form.salary_max) body.salary_max = parseInt(form.salary_max);
    if (form.client_company_name)
      body.client_company_name = form.client_company_name;
    if (form.client_id) body.client_id = parseInt(form.client_id);
    if (form.priority) body.priority = form.priority;
    if (form.positions_to_fill)
      body.positions_to_fill = parseInt(form.positions_to_fill);
    if (form.department) body.department = form.department;
    if (form.application_url) body.application_url = form.application_url;
    if (form.start_at)
      body.start_at = new Date(form.start_at).toISOString();
    if (form.closes_at)
      body.closes_at = new Date(form.closes_at).toISOString();
    if (form.job_id_external)
      body.job_id_external = form.job_id_external;

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/jobs`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowCreateForm(false);
        setForm({
          title: "",
          description: "",
          requirements: "",
          nice_to_haves: "",
          location: "",
          remote_policy: "",
          employment_type: "",
          salary_min: "",
          salary_max: "",
          client_company_name: "",
          client_id: "",
          priority: "normal",
          positions_to_fill: "1",
          department: "",
          application_url: "",
          start_at: "",
          closes_at: "",
          job_id_external: "",
          status: "active",
        });
        fetchJobs();
      } else {
        const data = await res.json();
        setError(parseApiError(data, "Failed to create job"));
      }
    } catch {
      setError("Network error");
    } finally {
      setCreating(false);
    }
  }

  function handleFileDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const allowed = [".docx", ".pdf"];
    const valid = Array.from(e.dataTransfer.files).filter((f) =>
      allowed.some((ext) => f.name.toLowerCase().endsWith(ext)),
    );
    if (valid.length > 0) {
      setUploadFiles((prev) => [...prev, ...valid]);
      setError("");
    } else {
      setError("Supported formats: .docx, .pdf");
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []);
    if (selected.length > 0) {
      setUploadFiles((prev) => [...prev, ...selected]);
      setError("");
    }
  }

  function startUploadPolling(batchId: string) {
    if (uploadPollRef.current) clearInterval(uploadPollRef.current);
    uploadPollRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/upload-batches/${batchId}/status`,
          { credentials: "include" }
        );
        if (!res.ok) return;
        const data = await res.json();
        setUploadBatchStatus(data);
        if (data.status === "completed") {
          if (uploadPollRef.current) clearInterval(uploadPollRef.current);
          uploadPollRef.current = null;
          setUploading(false);
          fetchJobs();
        }
      } catch {
        // Keep polling
      }
    }, 2000);
  }

  async function handleUpload() {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    syncProgress.start();
    setError("");
    setUploadBatchStatus(null);

    const formData = new FormData();
    uploadFiles.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/jobs/upload-documents`,
        { method: "POST", credentials: "include", body: formData }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(body?.detail || `Upload failed (${res.status})`);
        syncProgress.complete();
        setUploading(false);
        return;
      }
      const data = await res.json();

      if (data.batch_id) {
        // Async batch mode — poll for progress
        setUploadBatchStatus({
          batch_id: data.batch_id,
          status: "processing",
          total_files: data.total_files,
          files_completed: 0,
          files_succeeded: 0,
          files_failed: 0,
          files: uploadFiles.map((f) => ({
            filename: f.name, status: "pending", error: null, result: null,
          })),
        });
        setUploadFiles([]);
        syncProgress.complete();
        startUploadPolling(data.batch_id);
      } else {
        // Synchronous response — results are already available
        syncProgress.complete();
        setUploadBatchStatus({
          batch_id: "",
          status: "completed",
          total_files: data.total_submitted,
          files_completed: data.total_submitted,
          files_succeeded: data.total_succeeded,
          files_failed: data.total_failed,
          files: (data.results || []).map((r: { filename: string; success: boolean; error?: string; title?: string; job_id?: number }) => ({
            filename: r.filename,
            status: r.success ? "succeeded" : "failed",
            error: r.error || null,
            result: r.success ? { title: r.title, job_id: r.job_id } : null,
          })),
        });
        setUploadFiles([]);
        setUploading(false);
        fetchJobs();
      }
    } catch {
      setError("Network error during upload");
      syncProgress.complete();
      setUploading(false);
    }
  }

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            Recruiter Job Postings
          </h1>
          <p className="mt-1 text-slate-600">
            Post jobs for your clients and find matched candidates
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setShowUploadForm(!showUploadForm);
              if (!showUploadForm) setShowCreateForm(false);
            }}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {showUploadForm ? "Cancel Upload" : "Upload Documents"}
          </button>
          <button
            onClick={() => {
              setShowCreateForm(!showCreateForm);
              if (!showCreateForm) setShowUploadForm(false);
            }}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            {showCreateForm ? "Cancel" : "+ Create Job"}
          </button>
        </div>
      </div>

      {/* Upload Documents */}
      {showUploadForm && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Upload Job Documents
          </h2>
          <p className="mb-4 text-sm text-slate-500">
            Upload .docx or .pdf job descriptions. Our AI will parse them and
            create draft job postings automatically.
          </p>
          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors ${
              dragOver
                ? "border-blue-400 bg-blue-50"
                : "border-slate-200 bg-slate-50"
            }`}
          >
            <svg
              className="mb-3 h-10 w-10 text-slate-300"
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
              {uploadFiles.length > 0
                ? `${uploadFiles.length} file(s) selected`
                : "Drag files here, or click to browse"}
            </p>
            <p className="mb-3 text-xs text-slate-400">
              .docx or .pdf files only (max 10 MB each)
            </p>
            <input
              type="file"
              accept=".docx,.pdf"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              id="job-upload-input"
            />
            <label
              htmlFor="job-upload-input"
              className="cursor-pointer rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200"
            >
              Browse files
            </label>
          </div>

          {uploadFiles.length > 0 && (
            <div className="mt-4">
              <div className="mb-3 space-y-1">
                {uploadFiles.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-1.5 text-sm"
                  >
                    <span className="text-slate-700">{f.name}</span>
                    <button
                      onClick={() =>
                        setUploadFiles((prev) =>
                          prev.filter((_, idx) => idx !== i),
                        )
                      }
                      className="text-slate-400 hover:text-red-500"
                    >
                      x
                    </button>
                  </div>
                ))}
              </div>
              {!uploading ? (
                <button
                  onClick={handleUpload}
                  className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Upload & Parse {uploadFiles.length} file(s)
                </button>
              ) : (
                <div>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700">
                      {uploadBatchStatus && uploadBatchStatus.total_files > 0
                        ? `Processing ${uploadBatchStatus.files_completed} of ${uploadBatchStatus.total_files}...`
                        : `Uploading & parsing — ${syncProgress.pct}%`}
                    </span>
                    <span className="text-slate-500">
                      {uploadBatchStatus && uploadBatchStatus.total_files > 0
                        ? `${Math.round((uploadBatchStatus.files_completed / uploadBatchStatus.total_files) * 100)}%`
                        : `${syncProgress.pct}%`}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                    {uploadBatchStatus && uploadBatchStatus.total_files > 0 ? (
                      <div
                        className="h-full rounded-full bg-blue-600 transition-all duration-500 ease-out"
                        style={{
                          width: `${Math.max(2, Math.round((uploadBatchStatus.files_completed / uploadBatchStatus.total_files) * 100))}%`,
                        }}
                      />
                    ) : (
                      <div
                        className="h-full rounded-full bg-blue-600 transition-all duration-300 ease-out"
                        style={{ width: `${Math.max(2, syncProgress.pct)}%` }}
                      />
                    )}
                  </div>
                  <p className="mt-2 text-center text-xs text-slate-500">
                    AI is extracting job details from your document...
                  </p>
                </div>
              )}
            </div>
          )}

          {uploadBatchStatus && uploadBatchStatus.status === "completed" && (
            <div className="mt-4 space-y-2">
              <h3 className="text-sm font-semibold text-slate-700">
                Results — {uploadBatchStatus.files_succeeded}/{uploadBatchStatus.total_files} succeeded
              </h3>
              {uploadBatchStatus.files.map((r, i) => (
                <div
                  key={i}
                  className={`rounded-md px-3 py-2 text-sm ${
                    r.status === "succeeded"
                      ? "bg-green-50 text-green-700"
                      : "bg-red-50 text-red-700"
                  }`}
                >
                  <span className="font-medium">{r.filename}</span>
                  {r.status === "succeeded"
                    ? ` — Created: ${r.result?.title || "Job"} (draft)`
                    : ` — ${r.error || "Failed"}`}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create Job Form */}
      {showCreateForm && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            New Job Posting
          </h2>
          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}
          <form onSubmit={handleCreateJob} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Job Title *
                </label>
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) =>
                    setForm({ ...form, title: e.target.value })
                  }
                  required
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="e.g. Senior Software Engineer"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Client
                </label>
                {clients.length > 0 ? (
                  <select
                    value={form.client_id}
                    onChange={(e) =>
                      setForm({ ...form, client_id: e.target.value })
                    }
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  >
                    <option value="">No client</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.company_name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={form.client_company_name}
                    onChange={(e) =>
                      setForm({ ...form, client_company_name: e.target.value })
                    }
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                    placeholder="Company name"
                  />
                )}
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Description *
              </label>
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                required
                rows={4}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="Job description..."
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Requirements
              </label>
              <textarea
                value={form.requirements}
                onChange={(e) =>
                  setForm({ ...form, requirements: e.target.value })
                }
                rows={3}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="Required qualifications..."
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Location
                </label>
                <input
                  type="text"
                  value={form.location}
                  onChange={(e) =>
                    setForm({ ...form, location: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="e.g. New York, NY"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Remote Policy
                </label>
                <select
                  value={form.remote_policy}
                  onChange={(e) =>
                    setForm({ ...form, remote_policy: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="">Select...</option>
                  <option value="on-site">On-site</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="remote">Remote</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Employment Type
                </label>
                <select
                  value={form.employment_type}
                  onChange={(e) =>
                    setForm({ ...form, employment_type: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="">Select...</option>
                  <option value="full-time">Full-time</option>
                  <option value="part-time">Part-time</option>
                  <option value="contract">Contract</option>
                  <option value="internship">Internship</option>
                </select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Salary Min
                </label>
                <input
                  type="number"
                  value={form.salary_min}
                  onChange={(e) =>
                    setForm({ ...form, salary_min: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="e.g. 80000"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Salary Max
                </label>
                <input
                  type="number"
                  value={form.salary_max}
                  onChange={(e) =>
                    setForm({ ...form, salary_max: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="e.g. 120000"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Status
                </label>
                <select
                  value={form.status}
                  onChange={(e) =>
                    setForm({ ...form, status: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active (publish immediately)</option>
                </select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Priority
                </label>
                <select
                  value={form.priority}
                  onChange={(e) =>
                    setForm({ ...form, priority: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Positions to Fill
                </label>
                <input
                  type="number"
                  min="1"
                  value={form.positions_to_fill}
                  onChange={(e) =>
                    setForm({ ...form, positions_to_fill: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Department
                </label>
                <input
                  type="text"
                  value={form.department}
                  onChange={(e) =>
                    setForm({ ...form, department: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="e.g. Engineering"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Application URL
              </label>
              <input
                type="url"
                value={form.application_url}
                onChange={(e) =>
                  setForm({ ...form, application_url: e.target.value })
                }
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="https://..."
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Start Date
                </label>
                <input
                  type="date"
                  value={form.start_at}
                  onChange={(e) =>
                    setForm({ ...form, start_at: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Solicitation Number (Job ID) <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.job_id_external}
                  onChange={(e) =>
                    setForm({ ...form, job_id_external: e.target.value })
                  }
                  placeholder="e.g. SOL-2026-0042"
                  required
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Application Deadline <span className="text-red-500">*</span>
                </label>
                <input
                  type="date"
                  value={form.closes_at}
                  onChange={(e) =>
                    setForm({ ...form, closes_at: e.target.value })
                  }
                  required
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create Job"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search, sort, filter + bulk actions */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search title, company, contact, location..."
            className="w-64 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />

          <label className="text-sm font-medium text-slate-700">
            Status:
          </label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="closed">Closed</option>
            <option value="expired">Expired</option>
            <option value="no_deadline">No Deadline</option>
            <option value="no_job_id">No Job ID</option>
          </select>

          <label className="text-sm font-medium text-slate-700">
            Sort:
          </label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            <option value="created_at">Date Created</option>
            <option value="title">Title</option>
            <option value="closes_at">Deadline</option>
            <option value="client">Client</option>
            <option value="location">Location</option>
          </select>
          <button
            onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
            title={sortDir === "asc" ? "Ascending" : "Descending"}
          >
            {sortDir === "asc" ? "\u2191 Asc" : "\u2193 Desc"}
          </button>

          {jobs.length > 0 && (
            <>
              <div className="h-5 w-px bg-slate-200" />
              <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
                Select all ({jobs.length})
              </label>
            </>
          )}

          {selected.size > 0 && (
            <>
              <span className="text-sm font-medium text-slate-700">
                {selected.size} selected
              </span>
              <div className="h-5 w-px bg-slate-200" />
              <select
                value={bulkStatus}
                onChange={(e) => setBulkStatus(e.target.value)}
                className="rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="closed">Closed</option>
              </select>
              <button
                onClick={handleBulkStatusUpdate}
                disabled={bulkAction !== "idle"}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {bulkAction === "updating" ? "Applying..." : "Apply Status"}
              </button>
              <button
                onClick={handleBulkRefresh}
                disabled={bulkAction !== "idle"}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {bulkAction === "refreshing"
                  ? "Refreshing..."
                  : "Refresh Candidates"}
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={bulkAction !== "idle"}
                className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {bulkAction === "deleting"
                  ? "Deleting..."
                  : `Delete Selected (${selected.size})`}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Refresh banner */}
      {refreshBanner && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <span>{refreshBanner}</span>
          <button
            onClick={() => { setRefreshBanner(""); fetchJobs(); }}
            className="ml-4 rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
          >
            Dismiss &amp; Reload
          </button>
        </div>
      )}

      {/* Jobs List */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-xl font-semibold text-slate-900">No jobs yet</h3>
          <p className="mt-2 text-slate-600">
            Create your first job posting to start matching candidates.
          </p>
          <button
            onClick={() => setShowCreateForm(true)}
            className="mt-4 inline-block rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Create Your First Job
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <div
              key={job.id}
              className={`flex items-start gap-3 rounded-xl border bg-white p-5 shadow-sm transition-shadow hover:shadow-md ${
                selected.has(job.id)
                  ? "border-slate-400"
                  : "border-slate-200"
              }`}
            >
              {/* Checkbox */}
              <div
                className="flex items-center pt-1"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="checkbox"
                  checked={selected.has(job.id)}
                  onChange={() => toggleSelect(job.id)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
              </div>

              {/* Card content (navigable) */}
              <Link
                href={`/recruiter/jobs/${job.id}`}
                className="min-w-0 flex-1"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="mb-1 text-xs font-medium text-slate-400">
                      {job.job_id_external
                        ? `ID: ${job.job_id_external}`
                        : <span className="text-amber-500">No Job ID</span>}
                    </p>
                    <div className="mb-2 flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-slate-900">
                        {job.title}
                      </h3>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}
                      >
                        {job.status}
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-4 text-sm text-slate-500">
                      {job.client_company_name && (
                        <span>{job.client_company_name}</span>
                      )}
                      {job.location && <span>{job.location}</span>}
                      {job.remote_policy && (
                        <span className="capitalize">{job.remote_policy}</span>
                      )}
                      {job.employment_type && (
                        <span className="capitalize">
                          {job.employment_type}
                        </span>
                      )}
                      {(job.salary_min || job.salary_max) && (
                        <span>
                          {job.salary_min && job.salary_max
                            ? `$${job.salary_min.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} - $${job.salary_max.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                            : job.salary_max
                              ? `$${job.salary_max.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                              : `$${job.salary_min!.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                          {job.salary_max && (
                            <> (${(job.salary_max / 2080).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/hr)</>
                          )}
                        </span>
                      )}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-6 text-sm text-slate-500">
                      {job.matched_candidates_count > 0 && (
                        <span className="font-medium text-emerald-600">
                          {job.matched_candidates_count} matched candidates
                        </span>
                      )}
                      <span>
                        Created{" "}
                        {new Date(job.created_at).toLocaleDateString()}
                      </span>
                      {job.start_at && (
                        <span>
                          Starts{" "}
                          {new Date(job.start_at).toLocaleDateString(
                            undefined,
                            { month: "short", day: "numeric" },
                          )}
                        </span>
                      )}
                      {job.closes_at && (
                        <span>
                          Deadline{" "}
                          {new Date(job.closes_at).toLocaleDateString(
                            undefined,
                            { month: "short", day: "numeric" },
                          )}
                        </span>
                      )}
                    </div>
                  </div>

                  <svg
                    className="h-5 w-5 text-slate-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
