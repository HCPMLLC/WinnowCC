"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface RecruiterJob {
  id: number;
  title: string;
  description: string;
  requirements: string | null;
  nice_to_haves: string | null;
  client_company_name: string | null;
  client_id: number | null;
  client_name: string | null;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  status: string;
  application_url: string | null;
  application_email: string | null;
  priority: string | null;
  positions_to_fill: number;
  positions_filled: number;
  department: string | null;
  job_id_external: string | null;
  job_category: string | null;
  matched_candidates_count: number;
  posted_at: string | null;
  closes_at: string | null;
  start_at: string | null;
  created_at: string;
  employer_job_id: number | null;
  employer_company_name: string | null;
}

interface SubmissionCheck {
  already_submitted: boolean;
  submission_count: number;
  first_submitted_at: string | null;
  first_submitted_by: string | null;
}

interface Submission {
  id: number;
  recruiter_job_id: number;
  employer_job_id: number | null;
  candidate_profile_id: number;
  candidate_name: string;
  job_title: string | null;
  status: string;
  is_first_submission: boolean;
  submitted_at: string;
  employer_notes: string | null;
}

interface ClientOption {
  id: number;
  company_name: string;
}

interface CandidateMatch {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  matched_skills: string[];
  match_score: number;
  profile_visibility: string;
  in_pipeline: boolean;
}

interface CandidatesResponse {
  job_id: number;
  job_title: string;
  candidates: CandidateMatch[];
  total_cached: number;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800",
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  closed: "bg-red-100 text-red-800",
};

const inputCls =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

export default function RecruiterJobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const [job, setJob] = useState<RecruiterJob | null>(null);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [candidates, setCandidates] = useState<CandidateMatch[]>([]);
  const [totalCached, setTotalCached] = useState(0);
  const [loading, setLoading] = useState(true);
  const [autoPopulate, setAutoPopulate] = useState<boolean | null>(null);
  const [addedToPipeline, setAddedToPipeline] = useState<Set<number>>(new Set());
  const [addingId, setAddingId] = useState<number | null>(null);
  const [pipelineError, setPipelineError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshPercent, setRefreshPercent] = useState(0);
  const [refreshMessage, setRefreshMessage] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [submissionChecks, setSubmissionChecks] = useState<Record<number, SubmissionCheck>>({});
  const [submittingId, setSubmittingId] = useState<number | null>(null);

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
    job_id_external: "",
    job_category: "",
    application_url: "",
    start_at: "",
    closes_at: "",
    status: "draft",
  });

  function populateForm(j: RecruiterJob) {
    setForm({
      title: j.title || "",
      description: j.description || "",
      requirements: j.requirements || "",
      nice_to_haves: j.nice_to_haves || "",
      location: j.location || "",
      remote_policy: j.remote_policy || "",
      employment_type: j.employment_type || "",
      salary_min: j.salary_min?.toString() || "",
      salary_max: j.salary_max?.toString() || "",
      client_company_name: j.client_company_name || "",
      client_id: j.client_id?.toString() || "",
      priority: j.priority || "normal",
      positions_to_fill: j.positions_to_fill?.toString() || "1",
      department: j.department || "",
      job_id_external: j.job_id_external || "",
      job_category: j.job_category || "",
      application_url: j.application_url || "",
      start_at: j.start_at ? j.start_at.slice(0, 10) : "",
      closes_at: j.closes_at ? j.closes_at.slice(0, 10) : "",
      status: j.status || "draft",
    });
  }

  useEffect(() => {
    if (!jobId) return;

    Promise.all([
      fetch(`${API_BASE}/api/recruiter/jobs/${jobId}`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE}/api/recruiter/jobs/${jobId}/candidates?limit=50`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE}/api/recruiter/clients`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : [])),
      fetch(`${API_BASE}/api/recruiter/profile`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE}/api/recruiter/submissions?job_id=${jobId}`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([jobData, candData, clientData, profileData, subsData]) => {
        setJob(jobData);
        setClients(clientData || []);
        setSubmissions(subsData || []);
        if (candData) {
          setCandidates(candData.candidates);
          setTotalCached(candData.total_cached);
          // Initialize pipeline state from server
          const pipelined = new Set(
            (candData.candidates || [])
              .filter((c: CandidateMatch) => c.in_pipeline)
              .map((c: CandidateMatch) => c.id)
          );
          setAddedToPipeline(pipelined);
        }
        if (jobData) {
          populateForm(jobData);
        }
        if (profileData) {
          setAutoPopulate(profileData.auto_populate_pipeline ?? false);
        }
      })
      .finally(() => setLoading(false));
  }, [jobId]);

  async function handleRefreshCandidates() {
    setRefreshing(true);
    setRefreshPercent(0);
    setRefreshMessage("Starting...");
    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/jobs/${jobId}/refresh-candidates`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok || !res.body) {
        setRefreshMessage("Refresh failed");
        setRefreshing(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              setRefreshPercent(event.percent || 0);
              setRefreshMessage(event.message || "");
            } catch {
              // ignore parse errors
            }
          }
        }
      }

      // Reload candidates after refresh completes
      const candRes = await fetch(
        `${API_BASE}/api/recruiter/jobs/${jobId}/candidates?limit=50`,
        { credentials: "include" },
      );
      if (candRes.ok) {
        const data: CandidatesResponse = await candRes.json();
        setCandidates(data.candidates);
        setTotalCached(data.total_cached);
        // Update addedToPipeline from server state
        const pipelined = new Set(
          data.candidates.filter((c) => c.in_pipeline).map((c) => c.id)
        );
        setAddedToPipeline(pipelined);
      }
    } catch (err) {
      console.error("Refresh failed:", err);
      setRefreshMessage("Refresh failed");
    } finally {
      setRefreshing(false);
      setRefreshPercent(0);
      setRefreshMessage("");
    }
  }

  async function handleAddToPipeline(candidate: CandidateMatch) {
    setAddingId(candidate.id);
    setPipelineError("");
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/pipeline`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_profile_id: candidate.id,
          recruiter_job_id: parseInt(jobId),
          source: "job-match",
          stage: "sourced",
          match_score: candidate.match_score,
        }),
      });
      if (res.ok) {
        setAddedToPipeline((prev) => new Set(prev).add(candidate.id));
      } else if (res.status === 429) {
        const data = await res.json();
        setPipelineError(data.detail || "Pipeline limit reached. Upgrade your plan.");
      } else {
        const data = await res.json();
        setPipelineError(data.detail || "Failed to add to pipeline");
      }
    } catch {
      setPipelineError("Network error");
    } finally {
      setAddingId(null);
    }
  }

  async function handleStatusChange(newStatus: string) {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/jobs/${jobId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        const updated = await res.json();
        setJob(updated);
        populateForm(updated);
      }
    } catch (err) {
      console.error("Status update failed:", err);
    } finally {
      setSaving(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const body: Record<string, unknown> = {
      title: form.title,
      description: form.description,
      status: form.status,
    };
    if (form.requirements) body.requirements = form.requirements;
    else body.requirements = null;
    if (form.nice_to_haves) body.nice_to_haves = form.nice_to_haves;
    else body.nice_to_haves = null;
    if (form.location) body.location = form.location;
    else body.location = null;
    if (form.remote_policy) body.remote_policy = form.remote_policy;
    else body.remote_policy = null;
    if (form.employment_type) body.employment_type = form.employment_type;
    else body.employment_type = null;
    if (form.salary_min) body.salary_min = parseInt(form.salary_min);
    else body.salary_min = null;
    if (form.salary_max) body.salary_max = parseInt(form.salary_max);
    else body.salary_max = null;
    if (form.client_id) body.client_id = parseInt(form.client_id);
    if (form.client_company_name)
      body.client_company_name = form.client_company_name;
    if (form.priority) body.priority = form.priority;
    if (form.positions_to_fill)
      body.positions_to_fill = parseInt(form.positions_to_fill);
    if (form.department) body.department = form.department;
    else body.department = null;
    if (form.job_id_external) body.job_id_external = form.job_id_external;
    else body.job_id_external = null;
    if (form.job_category) body.job_category = form.job_category;
    else body.job_category = null;
    if (form.application_url) body.application_url = form.application_url;
    else body.application_url = null;
    body.start_at = form.start_at
      ? new Date(form.start_at).toISOString()
      : null;
    body.closes_at = form.closes_at
      ? new Date(form.closes_at).toISOString()
      : null;

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/jobs/${jobId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated = await res.json();
        setJob(updated);
        populateForm(updated);
        setEditing(false);
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to update job");
      }
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure you want to delete this job?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/jobs/${jobId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        router.push("/recruiter/jobs");
      }
    } catch (err) {
      console.error("Delete failed:", err);
    }
  }

  async function handleCheckAndSubmit(candidate: CandidateMatch) {
    if (!job?.employer_job_id) return;
    setSubmittingId(candidate.id);

    // Pre-submit check
    try {
      const checkRes = await fetch(
        `${API_BASE}/api/recruiter/jobs/${jobId}/submission-check/${candidate.id}`,
        { credentials: "include" },
      );
      if (checkRes.ok) {
        const check: SubmissionCheck = await checkRes.json();
        setSubmissionChecks((prev) => ({ ...prev, [candidate.id]: check }));
        if (check.already_submitted) {
          const proceed = confirm(
            `This candidate was already submitted by ${check.first_submitted_by} on ${check.first_submitted_at ? new Date(check.first_submitted_at).toLocaleDateString() : "unknown date"}. Submit anyway?`
          );
          if (!proceed) {
            setSubmittingId(null);
            return;
          }
        }
      }
    } catch {
      // continue with submission even if check fails
    }

    // Submit
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/submissions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recruiter_job_id: parseInt(jobId),
          candidate_profile_id: candidate.id,
        }),
      });
      if (res.ok) {
        const sub = await res.json();
        setSubmissions((prev) => [
          {
            id: sub.id,
            recruiter_job_id: sub.recruiter_job_id,
            employer_job_id: sub.employer_job_id,
            candidate_profile_id: sub.candidate_profile_id,
            candidate_name: candidate.name,
            job_title: job?.title || null,
            status: sub.status,
            is_first_submission: sub.is_first_submission,
            submitted_at: sub.submitted_at,
            employer_notes: null,
          },
          ...prev,
        ]);
      } else {
        const data = await res.json();
        setPipelineError(data.detail || "Failed to submit candidate");
      }
    } catch {
      setPipelineError("Network error");
    } finally {
      setSubmittingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading job details...</div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="py-20 text-center">
        <h2 className="text-xl font-semibold text-slate-900">Job not found</h2>
        <Link
          href="/recruiter/jobs"
          className="mt-4 inline-block text-sm text-slate-600 hover:text-slate-900"
        >
          Back to Jobs
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/recruiter/jobs"
            className="mb-2 inline-block text-sm text-slate-500 hover:text-slate-700"
          >
            &larr; Back to Jobs
          </Link>
          <h1 className="text-3xl font-bold text-slate-900">{job.title}</h1>
          <div className="mt-2 flex items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}
            >
              {job.status}
            </span>
            {(job.client_name || job.client_company_name) && (
              <span className="text-sm text-slate-600">
                {job.client_name || job.client_company_name}
              </span>
            )}
            {job.location && (
              <span className="text-sm text-slate-500">{job.location}</span>
            )}
            {job.remote_policy && (
              <span className="text-sm capitalize text-slate-500">
                {job.remote_policy}
              </span>
            )}
            {job.priority && job.priority !== "normal" && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${job.priority === "urgent" ? "bg-red-100 text-red-700" : job.priority === "high" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}
              >
                {job.priority}
              </span>
            )}
            {job.employer_job_id && (
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                Linked: {job.employer_company_name || `Employer Job #${job.employer_job_id}`}
              </span>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => {
              if (editing) {
                populateForm(job);
              }
              setEditing(!editing);
              setError("");
            }}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {editing ? "Cancel Edit" : "Edit"}
          </button>
          {!editing && (
            <>
              {job.status === "draft" && (
                <button
                  onClick={() => handleStatusChange("active")}
                  disabled={saving}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  Publish
                </button>
              )}
              {job.status === "active" && (
                <button
                  onClick={() => handleStatusChange("paused")}
                  disabled={saving}
                  className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                >
                  Pause
                </button>
              )}
              {job.status === "paused" && (
                <button
                  onClick={() => handleStatusChange("active")}
                  disabled={saving}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  Resume
                </button>
              )}
              {job.status !== "closed" && (
                <button
                  onClick={() => handleStatusChange("closed")}
                  disabled={saving}
                  className="rounded-md border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
                >
                  Close
                </button>
              )}
              <button
                onClick={handleDelete}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {/* Edit Form or Read-only Details */}
      {editing ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Edit Job Posting
          </h2>
          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}
          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Job ID / Solicitation #
                </label>
                <input
                  type="text"
                  value={form.job_id_external}
                  onChange={(e) =>
                    setForm({ ...form, job_id_external: e.target.value })
                  }
                  className={inputCls}
                  placeholder="e.g. DIR-CPO-TMP-445"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Category
                </label>
                <input
                  type="text"
                  value={form.job_category}
                  onChange={(e) =>
                    setForm({ ...form, job_category: e.target.value })
                  }
                  className={inputCls}
                  placeholder="e.g. Project Management, Engineering, IT"
                />
              </div>
            </div>

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
                  className={inputCls}
                  placeholder="e.g. Senior Software Engineer"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Client
                </label>
                <input
                  type="text"
                  value={form.client_company_name}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      client_company_name: e.target.value,
                    })
                  }
                  className={inputCls}
                  placeholder="Company name"
                />
                {clients.length > 0 && (
                  <select
                    value={form.client_id}
                    onChange={(e) => {
                      const selected = clients.find(
                        (c) => c.id === Number(e.target.value),
                      );
                      setForm({
                        ...form,
                        client_id: e.target.value,
                        client_company_name:
                          selected?.company_name || form.client_company_name,
                      });
                    }}
                    className={`${inputCls} mt-1`}
                  >
                    <option value="">Or link to existing client...</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.company_name}
                      </option>
                    ))}
                  </select>
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
                className={inputCls}
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
                className={inputCls}
                placeholder="Required qualifications..."
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Nice to Have
              </label>
              <textarea
                value={form.nice_to_haves}
                onChange={(e) =>
                  setForm({ ...form, nice_to_haves: e.target.value })
                }
                rows={2}
                className={inputCls}
                placeholder="Preferred qualifications..."
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
                  className={inputCls}
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
                  className={inputCls}
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
                  className={inputCls}
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
                  className={inputCls}
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
                  className={inputCls}
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
                  className={inputCls}
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="closed">Closed</option>
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
                  className={inputCls}
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
                  className={inputCls}
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
                  className={inputCls}
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
                className={inputCls}
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
                  className={inputCls}
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
                  className={inputCls}
                />
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  populateForm(job);
                  setEditing(false);
                  setError("");
                }}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Job Details
          </h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-slate-500">
                Description
              </h3>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                {job.description}
              </p>
            </div>
            {job.requirements && (
              <div>
                <h3 className="text-sm font-medium text-slate-500">
                  Requirements
                </h3>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                  {job.requirements}
                </p>
              </div>
            )}
            {job.nice_to_haves && (
              <div>
                <h3 className="text-sm font-medium text-slate-500">
                  Nice to Have
                </h3>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                  {job.nice_to_haves}
                </p>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-3">
              {job.job_id_external && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Job ID / Solicitation #
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {job.job_id_external}
                  </p>
                </div>
              )}
              {job.job_category && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Category
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {job.job_category}
                  </p>
                </div>
              )}
              {job.salary_min && job.salary_max && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Salary
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    ${job.salary_min.toLocaleString()} - $
                    {job.salary_max.toLocaleString()}{" "}
                    {job.salary_currency || "USD"}
                  </p>
                </div>
              )}
              {job.employment_type && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">Type</h3>
                  <p className="mt-1 text-sm capitalize text-slate-700">
                    {job.employment_type}
                  </p>
                </div>
              )}
              {job.posted_at && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Posted At
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {new Date(job.posted_at).toLocaleDateString()}
                  </p>
                </div>
              )}
              {job.start_at && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Start Date
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {new Date(job.start_at).toLocaleDateString()}
                  </p>
                </div>
              )}
              {job.closes_at && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Application Deadline
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {new Date(job.closes_at).toLocaleDateString()}
                  </p>
                </div>
              )}
              {job.positions_to_fill > 1 && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Positions
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {job.positions_filled} / {job.positions_to_fill} filled
                  </p>
                </div>
              )}
              {job.department && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Department
                  </h3>
                  <p className="mt-1 text-sm text-slate-700">
                    {job.department}
                  </p>
                </div>
              )}
              {job.application_url && (
                <div>
                  <h3 className="text-sm font-medium text-slate-500">
                    Application URL
                  </h3>
                  <a
                    href={job.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 text-sm text-blue-600 hover:underline"
                  >
                    {job.application_url}
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Submissions */}
      {submissions.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Submission History
          </h2>
          <div className="space-y-3">
            {submissions.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-lg border border-slate-200 p-4"
              >
                <div>
                  <span className="font-medium text-slate-900">
                    {s.candidate_name}
                  </span>
                  {s.job_title && (
                    <span className="ml-2 text-sm text-slate-500">
                      for {s.job_title}
                    </span>
                  )}
                  <div className="mt-1 flex gap-2 text-xs text-slate-400">
                    <span>
                      {s.submitted_at
                        ? new Date(s.submitted_at).toLocaleDateString()
                        : ""}
                    </span>
                    {s.is_first_submission && (
                      <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700">
                        First submission
                      </span>
                    )}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                    s.status === "accepted"
                      ? "bg-emerald-100 text-emerald-800"
                      : s.status === "rejected"
                        ? "bg-red-100 text-red-800"
                        : s.status === "withdrawn"
                          ? "bg-slate-100 text-slate-600"
                          : "bg-blue-100 text-blue-800"
                  }`}
                >
                  {s.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Matched Candidates */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Matched Candidates
            </h2>
            <p className="text-sm text-slate-500">
              {totalCached} candidate{totalCached !== 1 ? "s" : ""} scored above
              threshold
            </p>
          </div>
          <div className="flex items-center gap-3">
            {refreshing && (
              <div className="flex items-center gap-2">
                <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-slate-700 transition-all duration-300"
                    style={{ width: `${refreshPercent}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-slate-500 whitespace-nowrap">
                  {refreshPercent}%
                </span>
              </div>
            )}
            <button
              onClick={handleRefreshCandidates}
              disabled={refreshing}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {refreshing ? (refreshMessage || "Refreshing...") : "Refresh Matches"}
            </button>
          </div>
        </div>

        {candidates.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
            <p className="text-sm text-slate-600">
              {job.status === "active"
                ? "No matched candidates yet. Matches are computed asynchronously after publishing."
                : "Publish this job to start matching candidates."}
            </p>
          </div>
        ) : (
          <>
          {pipelineError && (
            <div className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{pipelineError}</div>
          )}
          <div className="space-y-3">
            {candidates.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between rounded-lg border border-slate-200 p-4 transition-colors hover:bg-slate-50"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">{c.name}</span>
                    {c.headline && (
                      <span className="text-sm text-slate-500">
                        {c.headline}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {c.matched_skills.slice(0, 8).map((skill) => (
                      <span
                        key={skill}
                        className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1 flex gap-4 text-xs text-slate-400">
                    {c.location && <span>{c.location}</span>}
                    {c.years_experience != null && (
                      <span>{c.years_experience} yrs exp</span>
                    )}
                  </div>
                </div>
                <div className="ml-4 flex items-center gap-3">
                  <div className="text-right">
                    <div className="text-lg font-bold text-slate-900">
                      {Math.round(c.match_score)}%
                    </div>
                    <div className="text-xs text-slate-500">match</div>
                  </div>
                  {addedToPipeline.has(c.id) || c.in_pipeline ? (
                    <span className="whitespace-nowrap rounded-md bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">
                      In Pipeline
                    </span>
                  ) : autoPopulate === false ? (
                    <button
                      onClick={() => handleAddToPipeline(c)}
                      disabled={addingId === c.id}
                      className="whitespace-nowrap rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
                    >
                      {addingId === c.id ? "Adding..." : "Add to Pipeline"}
                    </button>
                  ) : null}
                  {job.employer_job_id && !submissions.some(s => s.candidate_profile_id === c.id) && (
                    <button
                      onClick={() => handleCheckAndSubmit(c)}
                      disabled={submittingId === c.id}
                      className="whitespace-nowrap rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-50"
                    >
                      {submittingId === c.id ? "Submitting..." : "Submit to Employer"}
                    </button>
                  )}
                  {submissions.some(s => s.candidate_profile_id === c.id) && (
                    <span className="whitespace-nowrap rounded-md bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700">
                      Submitted
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
          </>
        )}
      </div>
    </div>
  );
}
