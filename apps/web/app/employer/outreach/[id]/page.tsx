"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Enrollment {
  id: number;
  candidate_profile_id: number;
  current_step: number;
  status: string;
  next_send_at: string | null;
  last_sent_at: string | null;
  enrolled_at: string | null;
  candidate_name: string | null;
  candidate_email: string | null;
}

interface Sequence {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  employer_job_id: number | null;
  steps: Record<string, unknown>[];
  enrolled_count: number;
  sent_count: number;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  completed: "bg-blue-100 text-blue-800",
  unenrolled: "bg-slate-100 text-slate-600",
  bounced: "bg-red-100 text-red-800",
  applied: "bg-purple-100 text-purple-800",
};

export default function SequenceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sequenceId = params.id as string;

  const [sequence, setSequence] = useState<Sequence | null>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/employer/outreach/sequences/${sequenceId}`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : null)),
      fetch(
        `${API_BASE}/api/employer/outreach/sequences/${sequenceId}/enrollments`,
        { credentials: "include" },
      ).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([seq, enr]) => {
        setSequence(seq);
        setEnrollments(enr);
      })
      .finally(() => setLoading(false));
  }, [sequenceId]);

  async function handleDelete() {
    if (!confirm("Delete this sequence and all enrollments?")) return;
    const res = await fetch(
      `${API_BASE}/api/employer/outreach/sequences/${sequenceId}`,
      { method: "DELETE", credentials: "include" },
    );
    if (res.ok) router.push("/employer/outreach");
  }

  async function toggleActive() {
    if (!sequence) return;
    const res = await fetch(
      `${API_BASE}/api/employer/outreach/sequences/${sequenceId}`,
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !sequence.is_active }),
      },
    );
    if (res.ok) {
      const updated = await res.json();
      setSequence(updated);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl py-8">
        <div className="h-40 animate-pulse rounded-lg bg-slate-100" />
      </div>
    );
  }

  if (!sequence) {
    return (
      <div className="mx-auto max-w-4xl py-8">
        <p className="text-slate-500">Sequence not found.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 py-8">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/employer/outreach"
            className="text-xs text-blue-600 hover:text-blue-700"
          >
            &larr; All Sequences
          </Link>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">
            {sequence.name}
          </h1>
          {sequence.description && (
            <p className="mt-1 text-sm text-slate-500">
              {sequence.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleActive}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              sequence.is_active
                ? "bg-amber-100 text-amber-800 hover:bg-amber-200"
                : "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
            }`}
          >
            {sequence.is_active ? "Pause" : "Activate"}
          </button>
          <button
            onClick={handleDelete}
            className="rounded-md bg-red-100 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Steps */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">
          Steps ({sequence.steps.length})
        </h2>
        <div className="space-y-2">
          {sequence.steps.map((step, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-md bg-slate-50 p-3 text-sm"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-800">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-800">
                  {String(step.subject || "")}
                </p>
                <p className="text-xs text-slate-500">
                  Delay: {String(step.delay_days || 0)} day(s) | Action:{" "}
                  {String(step.action || "followup")}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Enrollments */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">
          Enrollments ({enrollments.length})
        </h2>
        {enrollments.length === 0 ? (
          <p className="text-sm text-slate-500">
            No candidates enrolled yet.
          </p>
        ) : (
          <div className="space-y-2">
            {enrollments.map((e) => (
              <div
                key={e.id}
                className="flex items-center justify-between rounded-md bg-slate-50 p-3 text-sm"
              >
                <div>
                  <p className="font-medium text-slate-800">
                    {e.candidate_name || `Candidate #${e.candidate_profile_id}`}
                  </p>
                  {e.candidate_email && (
                    <p className="text-xs text-slate-500">
                      {e.candidate_email}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">
                    Step {e.current_step + 1}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[e.status] || "bg-slate-100 text-slate-600"}`}
                  >
                    {e.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
