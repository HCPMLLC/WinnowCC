"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface OutreachSequence {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  employer_job_id: number | null;
  enrolled_count: number;
  sent_count: number;
  steps: Record<string, unknown>[];
  created_at: string | null;
}

export default function OutreachListPage() {
  const [sequences, setSequences] = useState<OutreachSequence[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/employer/outreach/sequences`, {
      credentials: "include",
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSequences)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">
          Outreach Sequences
        </h1>
        <Link
          href="/employer/outreach/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          New Sequence
        </Link>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-lg bg-slate-100"
            />
          ))}
        </div>
      ) : sequences.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
          <p className="text-sm text-slate-500">
            No outreach sequences yet. Create one to start reaching out to
            candidates.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {sequences.map((seq) => (
            <Link
              key={seq.id}
              href={`/employer/outreach/${seq.id}`}
              className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-300"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    {seq.name}
                  </h3>
                  {seq.description && (
                    <p className="mt-0.5 text-xs text-slate-500">
                      {seq.description}
                    </p>
                  )}
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${seq.is_active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}
                >
                  {seq.is_active ? "Active" : "Paused"}
                </span>
              </div>
              <div className="mt-2 flex gap-4 text-xs text-slate-500">
                <span>{seq.steps.length} step(s)</span>
                <span>{seq.enrolled_count} enrolled</span>
                <span>{seq.sent_count} sent</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
