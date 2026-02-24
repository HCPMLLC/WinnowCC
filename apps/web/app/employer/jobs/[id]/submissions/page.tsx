"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Submission {
  id: number;
  candidate_profile_id: number;
  candidate_name: string;
  recruiter_profile_id: number;
  recruiter_company_name: string | null;
  submitted_at: string;
  is_first_submission: boolean;
  status: string;
  employer_notes: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  submitted: "bg-blue-100 text-blue-800",
  under_review: "bg-amber-100 text-amber-800",
  accepted: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
  withdrawn: "bg-slate-100 text-slate-600",
};

export default function EmployerJobSubmissionsPage() {
  const params = useParams();
  const jobId = params.id as string;

  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<number | null>(null);

  useEffect(() => {
    if (!jobId) return;
    fetch(`${API_BASE}/api/employer/jobs/${jobId}/submissions`, {
      credentials: "include",
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setSubmissions(data))
      .finally(() => setLoading(false));
  }, [jobId]);

  async function handleStatusUpdate(subId: number, newStatus: string) {
    setUpdating(subId);
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/submissions/${subId}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        },
      );
      if (res.ok) {
        setSubmissions((prev) =>
          prev.map((s) => (s.id === subId ? { ...s, status: newStatus } : s)),
        );
      }
    } catch {
      /* ignore */
    } finally {
      setUpdating(null);
    }
  }

  // Group candidates to highlight duplicates
  const candidateCounts: Record<number, number> = {};
  for (const s of submissions) {
    candidateCounts[s.candidate_profile_id] =
      (candidateCounts[s.candidate_profile_id] || 0) + 1;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading submissions...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/employer/jobs/${jobId}`}
          className="mb-2 inline-block text-sm text-slate-500 hover:text-slate-700"
        >
          &larr; Back to Job
        </Link>
        <h1 className="text-3xl font-bold text-slate-900">
          Recruiter Submissions
        </h1>
        <p className="mt-1 text-slate-600">
          {submissions.length} submission{submissions.length !== 1 ? "s" : ""}{" "}
          from recruiters
        </p>
      </div>

      {submissions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-xl font-semibold text-slate-900">
            No submissions yet
          </h3>
          <p className="mt-2 text-slate-600">
            Recruiters haven&apos;t submitted any candidates for this job yet.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 text-left text-sm text-slate-500">
                <th className="px-6 py-3 font-medium">Candidate</th>
                <th className="px-6 py-3 font-medium">Recruiter</th>
                <th className="px-6 py-3 font-medium">Submitted</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => {
                const isDuplicate =
                  candidateCounts[s.candidate_profile_id] > 1;
                return (
                  <tr
                    key={s.id}
                    className={`border-b border-slate-100 ${isDuplicate ? "bg-amber-50/50" : ""}`}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900">
                          {s.candidate_name}
                        </span>
                        {s.is_first_submission && (
                          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-700">
                            1st
                          </span>
                        )}
                        {isDuplicate && !s.is_first_submission && (
                          <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700">
                            Duplicate
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {s.recruiter_company_name || "Unknown"}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">
                      {s.submitted_at
                        ? new Date(s.submitted_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[s.status] ?? "bg-slate-100 text-slate-600"}`}
                      >
                        {s.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {s.status === "submitted" && (
                        <div className="flex gap-2">
                          <button
                            onClick={() =>
                              handleStatusUpdate(s.id, "accepted")
                            }
                            disabled={updating === s.id}
                            className="rounded-md bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                          >
                            Accept
                          </button>
                          <button
                            onClick={() =>
                              handleStatusUpdate(s.id, "rejected")
                            }
                            disabled={updating === s.id}
                            className="rounded-md bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
