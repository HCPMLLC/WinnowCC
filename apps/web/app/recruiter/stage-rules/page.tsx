"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface StageRule {
  id: number;
  from_stage: string;
  to_stage: string;
  condition_type: string;
  condition_value: string;
  is_active: boolean;
  recruiter_job_id: number | null;
}

interface RecruiterJob {
  id: number;
  title: string;
}

const STAGES = ["sourced", "qualified", "interviewing", "offered", "hired", "rejected"];

const CONDITION_TYPES = [
  { value: "match_score_above", label: "Match score above" },
  { value: "rating_above", label: "Rating above" },
  { value: "days_in_stage", label: "Days in stage exceeds" },
  { value: "tag_present", label: "Tag is present" },
];

const STAGE_COLORS: Record<string, string> = {
  sourced: "bg-slate-100 text-slate-700",
  qualified: "bg-blue-100 text-blue-700",
  interviewing: "bg-purple-100 text-purple-700",
  offered: "bg-emerald-100 text-emerald-700",
  hired: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

function conditionLabel(type: string, value: string): string {
  switch (type) {
    case "match_score_above":
      return `Match score >= ${value}`;
    case "rating_above":
      return `Rating >= ${value} stars`;
    case "days_in_stage":
      return `${value}+ days in stage`;
    case "tag_present":
      return `Tag "${value}" present`;
    default:
      return `${type}: ${value}`;
  }
}

export default function RecruiterStageRulesPage() {
  const [rules, setRules] = useState<StageRule[]>([]);
  const [jobs, setJobs] = useState<RecruiterJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [applyResult, setApplyResult] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  const [form, setForm] = useState({
    from_stage: "sourced",
    to_stage: "qualified",
    condition_type: "match_score_above",
    condition_value: "",
    recruiter_job_id: "",
  });

  const fetchRules = () => {
    fetch(`${API_BASE}/api/recruiter/stage-rules`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : { rules: [] }))
      .then((data) => setRules(data.rules ?? []))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRules();
    fetch(`${API_BASE}/api/recruiter/jobs`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setJobs(Array.isArray(data) ? data : data.jobs ?? []))
      .catch(() => {});
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    const body: Record<string, unknown> = {
      from_stage: form.from_stage,
      to_stage: form.to_stage,
      condition_type: form.condition_type,
      condition_value: form.condition_value,
    };
    if (form.recruiter_job_id) body.recruiter_job_id = Number(form.recruiter_job_id);

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/stage-rules`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowForm(false);
        setForm({
          from_stage: "sourced",
          to_stage: "qualified",
          condition_type: "match_score_above",
          condition_value: "",
          recruiter_job_id: "",
        });
        fetchRules();
      } else {
        const data = await res.json().catch(() => null);
        setError(data?.detail || `Failed to create rule (${res.status})`);
      }
    } catch {
      setError("Network error");
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (rule: StageRule) => {
    try {
      await fetch(`${API_BASE}/api/recruiter/stage-rules/${rule.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !rule.is_active }),
      });
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, is_active: !r.is_active } : r)),
      );
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this rule?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/stage-rules/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok || res.status === 204) {
        setRules((prev) => prev.filter((r) => r.id !== id));
      }
    } catch {
      /* ignore */
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setApplyResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/stage-rules/apply`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setApplyResult(`${data.advanced} candidate${data.advanced !== 1 ? "s" : ""} advanced`);
        setTimeout(() => setApplyResult(null), 3000);
      }
    } catch {
      setApplyResult("Failed to apply rules");
      setTimeout(() => setApplyResult(null), 3000);
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading stage rules...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Stage Rules</h1>
          <p className="mt-1 text-sm text-slate-500">
            Automate pipeline advancement based on conditions
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleApply}
            disabled={applying || rules.length === 0}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {applying ? "Applying..." : "Apply Rules Now"}
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            {showForm ? "Cancel" : "+ New Rule"}
          </button>
        </div>
      </div>

      {/* Apply result banner */}
      {applyResult && (
        <div className="rounded-md bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
          {applyResult}
        </div>
      )}

      {/* Create form */}
      {showForm && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Create Rule</h2>
          {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">From Stage</label>
                <select
                  value={form.from_stage}
                  onChange={(e) => setForm({ ...form, from_stage: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm capitalize focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  {STAGES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">To Stage</label>
                <select
                  value={form.to_stage}
                  onChange={(e) => setForm({ ...form, to_stage: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm capitalize focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  {STAGES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Condition</label>
                <select
                  value={form.condition_type}
                  onChange={(e) => setForm({ ...form, condition_type: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  {CONDITION_TYPES.map((ct) => (
                    <option key={ct.value} value={ct.value}>
                      {ct.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Value</label>
                <input
                  type="text"
                  required
                  value={form.condition_value}
                  onChange={(e) => setForm({ ...form, condition_value: e.target.value })}
                  placeholder={
                    form.condition_type === "tag_present"
                      ? "e.g. senior"
                      : form.condition_type === "days_in_stage"
                        ? "e.g. 7"
                        : "e.g. 80"
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </div>
            </div>
            <div className="flex items-end gap-4">
              <div className="w-64">
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Job (optional)
                </label>
                <select
                  value={form.recruiter_job_id}
                  onChange={(e) => setForm({ ...form, recruiter_job_id: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="">All Jobs</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  {creating ? "Saving..." : "Save Rule"}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Rules list */}
      {rules.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <p className="text-lg font-medium text-slate-600">No stage rules yet</p>
          <p className="mt-1 text-sm text-slate-400">
            Create rules to automatically advance candidates through your pipeline based on
            conditions like match score, rating, or time in stage.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`rounded-xl border bg-white p-5 shadow-sm transition-colors ${
                rule.is_active ? "border-slate-200" : "border-slate-100 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  {/* Stage transition badges */}
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                      STAGE_COLORS[rule.from_stage] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {rule.from_stage}
                  </span>
                  <span className="text-slate-300">&rarr;</span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                      STAGE_COLORS[rule.to_stage] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {rule.to_stage}
                  </span>
                  {/* Condition */}
                  <span className="text-sm text-slate-600">
                    when {conditionLabel(rule.condition_type, rule.condition_value)}
                  </span>
                  {rule.recruiter_job_id && (
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                      Job #{rule.recruiter_job_id}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {/* Active toggle */}
                  <button
                    onClick={() => handleToggle(rule)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      rule.is_active ? "bg-emerald-500" : "bg-slate-300"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        rule.is_active ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(rule.id)}
                    className="text-slate-400 hover:text-red-500"
                    title="Delete rule"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
