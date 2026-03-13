"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface FormResponse {
  id: number;
  job_form_id: number;
  user_id: number;
  candidate_name: string | null;
  form_type: string | null;
  original_filename: string | null;
  status: string;
  created_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  reviewed: "bg-blue-100 text-blue-800",
  accepted: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
};

export default function FormResponsesTab({ jobId }: { jobId: string }) {
  const [responses, setResponses] = useState<FormResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    fetchResponses();
  }, [jobId, statusFilter]);

  async function fetchResponses() {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set("status_filter", statusFilter);
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${jobId}/form-responses?${params}`,
        { credentials: "include" },
      );
      if (res.ok) setResponses(await res.json());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(responseId: number, newStatus: string) {
    const res = await fetch(
      `${API_BASE}/api/employer/jobs/${jobId}/form-responses/${responseId}/status`,
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      },
    );
    if (res.ok) fetchResponses();
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">
          Form Responses
        </h2>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-xs"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="completed">Completed</option>
          <option value="reviewed">Reviewed</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded-md bg-slate-100"
            />
          ))}
        </div>
      ) : responses.length === 0 ? (
        <p className="text-sm text-slate-500">No form responses yet.</p>
      ) : (
        <div className="space-y-2">
          {responses.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 p-3"
            >
              <div>
                <p className="text-sm font-medium text-slate-800">
                  {r.candidate_name || `User #${r.user_id}`}
                </p>
                <p className="text-xs text-slate-500">
                  {r.original_filename || r.form_type || "Form"} &mdash;{" "}
                  {r.created_at
                    ? new Date(r.created_at).toLocaleDateString()
                    : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[r.status] || "bg-slate-100 text-slate-600"}`}
                >
                  {r.status}
                </span>
                {r.status !== "accepted" && r.status !== "rejected" && (
                  <div className="flex gap-1">
                    <button
                      onClick={() => updateStatus(r.id, "accepted")}
                      className="rounded px-2 py-1 text-[10px] font-medium text-emerald-700 hover:bg-emerald-100"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => updateStatus(r.id, "rejected")}
                      className="rounded px-2 py-1 text-[10px] font-medium text-red-700 hover:bg-red-100"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
