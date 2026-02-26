"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface PipelineEntry {
  id: number;
  candidate_profile_id: number;
  pipeline_status: string;
  match_score: number | null;
  tags: string[];
  notes: string | null;
  source_job_id: number | null;
  last_contacted_at: string | null;
  next_followup_at: string | null;
  consent_given: boolean;
  created_at: string | null;
}

const STATUSES = [
  "silver_medalist",
  "warm_lead",
  "nurturing",
  "contacted",
  "hired",
];

const STATUS_LABELS: Record<string, string> = {
  silver_medalist: "Silver Medalist",
  warm_lead: "Warm Lead",
  nurturing: "Nurturing",
  contacted: "Contacted",
  hired: "Hired",
  not_interested: "Not Interested",
};

const STATUS_COLORS: Record<string, string> = {
  silver_medalist: "bg-amber-100 text-amber-800 border-amber-200",
  warm_lead: "bg-blue-100 text-blue-800 border-blue-200",
  nurturing: "bg-purple-100 text-purple-800 border-purple-200",
  contacted: "bg-emerald-100 text-emerald-800 border-emerald-200",
  hired: "bg-green-100 text-green-800 border-green-200",
  not_interested: "bg-slate-100 text-slate-600 border-slate-200",
};

export default function PipelinePage() {
  const [entries, setEntries] = useState<PipelineEntry[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPipeline();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchPipeline is a closure over filter, already tracked
  }, [filter]);

  async function fetchPipeline() {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter) params.set("status", filter);
      const res = await fetch(
        `${API_BASE}/api/employer/pipeline?${params}`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("Failed to load pipeline");
      setEntries(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setIsLoading(false);
    }
  }

  async function updateStatus(id: number, newStatus: string) {
    try {
      const res = await fetch(`${API_BASE}/api/employer/pipeline/${id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline_status: newStatus }),
      });
      if (res.ok) fetchPipeline();
    } catch {
      // Ignore
    }
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  // Group by status for Kanban view
  const grouped: Record<string, PipelineEntry[]> = {};
  for (const status of STATUSES) {
    grouped[status] = entries.filter((e) => e.pipeline_status === status);
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            Talent Pipeline
          </h1>
          <p className="mt-1 text-slate-600">
            Manage your silver medalists and warm leads
          </p>
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {STATUSES.map((s) => (
            <div
              key={s}
              className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {STATUSES.map((status) => (
            <div
              key={status}
              className="rounded-xl border border-slate-200 bg-slate-50 p-3"
            >
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${STATUS_COLORS[status]}`}
                >
                  {grouped[status]?.length ?? 0}
                </span>
                {STATUS_LABELS[status]}
              </h3>
              <div className="space-y-2">
                {(grouped[status] || []).map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  >
                    <p className="text-sm font-medium text-slate-900">
                      Candidate #{entry.candidate_profile_id}
                    </p>
                    {entry.match_score != null && (
                      <p className="text-xs text-slate-500">
                        Match: {entry.match_score}%
                      </p>
                    )}
                    {entry.tags.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {entry.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <select
                      value={entry.pipeline_status}
                      onChange={(e) =>
                        updateStatus(entry.id, e.target.value)
                      }
                      className="mt-2 w-full rounded border border-slate-200 px-2 py-1 text-xs"
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABELS[s]}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
