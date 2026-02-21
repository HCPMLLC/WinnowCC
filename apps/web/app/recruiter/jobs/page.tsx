"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

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
  priority: string | null;
  positions_to_fill: number;
  positions_filled: number;
  department: string | null;
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
  const [statusFilter, setStatusFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadPhase, setUploadPhase] = useState<"upload" | "parsing">(
    "upload",
  );
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadResults, setUploadResults] = useState<
    { filename: string; success: boolean; title?: string; error?: string }[]
  >([]);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkAction, setBulkAction] = useState<"idle" | "deleting" | "updating">("idle");
  const [bulkStatus, setBulkStatus] = useState("active");

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
    status: "active",
  });

  async function fetchJobs() {
    try {
      const url = new URL(`${API_BASE}/api/recruiter/jobs`);
      if (statusFilter) url.searchParams.set("status", statusFilter);
      const res = await fetch(url.toString(), { credentials: "include" });
      if (res.ok) {
        setJobs(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    }
  }

  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      fetchJobs(),
      fetch(`${API_BASE}/api/recruiter/clients`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : []))
        .then((data) => setClients(data))
        .catch(() => {}),
    ]).finally(() => setIsLoading(false));
  }, [statusFilter]);

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

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} job${selected.size !== 1 ? "s" : ""}? This cannot be undone.`)) return;

    setBulkAction("deleting");
    try {
      const params = new URLSearchParams();
      for (const id of selected) params.append("ids", String(id));
      const res = await fetch(`${API_BASE}/api/recruiter/jobs/bulk-delete?${params.toString()}`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        setSelected(new Set());
        fetchJobs();
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to delete jobs");
      }
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
      const params = new URLSearchParams();
      for (const id of selected) params.append("ids", String(id));
      params.append("new_status", bulkStatus);
      const res = await fetch(`${API_BASE}/api/recruiter/jobs/bulk-status?${params.toString()}`, {
        method: "PATCH",
        credentials: "include",
      });
      if (res.ok) {
        setSelected(new Set());
        fetchJobs();
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to update jobs");
      }
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
          status: "active",
        });
        fetchJobs();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to create job");
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
    const allowed = [".doc", ".docx", ".pdf", ".txt"];
    const valid = Array.from(e.dataTransfer.files).filter((f) =>
      allowed.some((ext) => f.name.toLowerCase().endsWith(ext)),
    );
    if (valid.length > 0) {
      setUploadFiles((prev) => [...prev, ...valid]);
      setError("");
    } else {
      setError("Supported formats: .doc, .docx, .pdf, .txt");
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []);
    if (selected.length > 0) {
      setUploadFiles((prev) => [...prev, ...selected]);
      setError("");
    }
  }

  function handleUpload() {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    setUploadPct(0);
    setUploadPhase("upload");
    setError("");
    setUploadResults([]);

    const formData = new FormData();
    uploadFiles.forEach((f) => formData.append("files", f));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/recruiter/jobs/upload-documents`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        setUploadPct(pct);
        if (pct >= 100) setUploadPhase("parsing");
      }
    };

    xhr.onload = () => {
      setUploadPct(100);
      if (xhr.status >= 200 && xhr.status < 300) {
        const data = JSON.parse(xhr.responseText);
        setUploadResults(data.results || []);
        setUploadFiles([]);
        fetchJobs();
      } else {
        try {
          const data = JSON.parse(xhr.responseText);
          setError(data.detail || "Upload failed");
        } catch {
          setError(`Upload failed (${xhr.status})`);
        }
      }
      setUploading(false);
    };

    xhr.onerror = () => {
      setError("Network error during upload");
      setUploading(false);
    };

    xhr.send(formData);
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
            Upload .doc, .docx, .pdf, or .txt job descriptions. Our AI will
            parse them and create draft job postings automatically.
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
                : "Drop files here, or click to browse"}
            </p>
            <p className="mb-3 text-xs text-slate-400">
              .doc, .docx, .pdf, .txt (max 10 MB each)
            </p>
            <input
              type="file"
              accept=".doc,.docx,.pdf,.txt"
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
                      {uploadPhase === "upload"
                        ? "Uploading files..."
                        : "AI is parsing documents..."}
                    </span>
                    <span className="text-slate-500">
                      {uploadPhase === "upload" ? `${uploadPct}%` : ""}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ease-out ${
                        uploadPhase === "parsing"
                          ? "animate-pulse bg-amber-500"
                          : "bg-blue-600"
                      }`}
                      style={{
                        width:
                          uploadPhase === "parsing"
                            ? "100%"
                            : `${uploadPct}%`,
                      }}
                    />
                  </div>
                  {uploadPhase === "parsing" && (
                    <p className="mt-2 text-center text-xs text-slate-500">
                      This may take a moment per file...
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {uploadResults.length > 0 && (
            <div className="mt-4 space-y-2">
              <h3 className="text-sm font-semibold text-slate-700">Results</h3>
              {uploadResults.map((r, i) => (
                <div
                  key={i}
                  className={`rounded-md px-3 py-2 text-sm ${
                    r.success
                      ? "bg-green-50 text-green-700"
                      : "bg-red-50 text-red-700"
                  }`}
                >
                  <span className="font-medium">{r.filename}</span>
                  {r.success
                    ? ` — Created: ${r.title} (draft)`
                    : ` — ${r.error}`}
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
                  Application Deadline
                </label>
                <input
                  type="date"
                  value={form.closes_at}
                  onChange={(e) =>
                    setForm({ ...form, closes_at: e.target.value })
                  }
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

      {/* Status filter + bulk actions */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          <label className="text-sm font-medium text-slate-700">
            Filter by status:
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
          </select>

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
                      {job.salary_min && job.salary_max && (
                        <span>
                          ${job.salary_min.toLocaleString()} - $
                          {job.salary_max.toLocaleString()}
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
