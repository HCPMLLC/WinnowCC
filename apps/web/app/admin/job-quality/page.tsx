"use client";

import { useEffect, useState } from "react";

type RedFlag = {
  code: string;
  severity: string;
  description: string;
  points: number;
};

type FlaggedJob = {
  job_id: number;
  title: string;
  company: string;
  fraud_score: number | null;
  posting_quality_score: number | null;
  is_likely_fraudulent: boolean | null;
  red_flags: RedFlag[] | null;
  is_stale: boolean | null;
  parsed_at: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function AdminJobQualityPage() {
  const [jobs, setJobs] = useState<FlaggedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);
  const [actionStatus, setActionStatus] = useState<Record<number, string>>({});

  useEffect(() => {
    const fetchFlagged = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/admin/jobs/flagged`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load flagged jobs.");
        }
        const data = (await response.json()) as FlaggedJob[];
        setJobs(data);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    void fetchFlagged();
  }, []);

  const handleFraudOverride = async (
    jobId: number,
    isFraudulent: boolean
  ) => {
    setActionStatus((prev) => ({
      ...prev,
      [jobId]: isFraudulent ? "Marking fraudulent..." : "Marking legitimate...",
    }));
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/jobs/${jobId}/fraud-override`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ is_fraudulent: isFraudulent }),
        }
      );
      if (!response.ok) {
        throw new Error("Failed to update.");
      }
      setActionStatus((prev) => ({
        ...prev,
        [jobId]: isFraudulent ? "Marked Fraudulent" : "Marked Legitimate",
      }));
      // Update local state
      setJobs((prev) =>
        prev.map((j) =>
          j.job_id === jobId
            ? { ...j, is_likely_fraudulent: isFraudulent }
            : j
        )
      );
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed.";
      setActionStatus((prev) => ({ ...prev, [jobId]: message }));
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <p className="text-slate-500">Loading flagged jobs...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Job Quality Review
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Jobs with fraud score &ge; 40 flagged for review
            </p>
          </div>
          <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-800">
            {jobs.length} flagged
          </span>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {jobs.length === 0 && !error ? (
          <div className="rounded-lg border border-slate-200 bg-white p-12 text-center">
            <p className="text-slate-500">
              No flagged jobs found. All postings look clean.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="rounded-lg border border-slate-200 bg-white shadow-sm"
              >
                {/* Row */}
                <div
                  className="flex cursor-pointer items-center justify-between px-5 py-4"
                  onClick={() =>
                    setExpandedJobId(
                      expandedJobId === job.job_id ? null : job.job_id
                    )
                  }
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="truncate text-sm font-semibold text-slate-900">
                        {job.title}
                      </h3>
                      {job.is_likely_fraudulent && (
                        <span className="shrink-0 rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                          Fraudulent
                        </span>
                      )}
                      {job.is_stale && (
                        <span className="shrink-0 rounded bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
                          Stale
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-500">{job.company}</p>
                  </div>

                  <div className="flex items-center gap-4">
                    {/* Fraud Score */}
                    <div className="text-center">
                      <span
                        className={`text-lg font-bold ${
                          (job.fraud_score ?? 0) >= 60
                            ? "text-red-600"
                            : (job.fraud_score ?? 0) >= 40
                              ? "text-amber-600"
                              : "text-green-600"
                        }`}
                      >
                        {job.fraud_score ?? 0}
                      </span>
                      <p className="text-xs text-slate-400">Fraud</p>
                    </div>

                    {/* Quality Score */}
                    <div className="text-center">
                      <span
                        className={`text-lg font-bold ${
                          (job.posting_quality_score ?? 0) >= 70
                            ? "text-green-600"
                            : (job.posting_quality_score ?? 0) >= 40
                              ? "text-amber-600"
                              : "text-red-600"
                        }`}
                      >
                        {job.posting_quality_score ?? 0}
                      </span>
                      <p className="text-xs text-slate-400">Quality</p>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFraudOverride(job.job_id, true);
                        }}
                        className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
                      >
                        Fraudulent
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFraudOverride(job.job_id, false);
                        }}
                        className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                      >
                        Legitimate
                      </button>
                    </div>

                    {/* Expand arrow */}
                    <svg
                      className={`h-5 w-5 text-slate-400 transition-transform ${
                        expandedJobId === job.job_id ? "rotate-180" : ""
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </div>
                </div>

                {/* Expanded details */}
                {expandedJobId === job.job_id && (
                  <div className="border-t border-slate-100 px-5 py-4">
                    {actionStatus[job.job_id] && (
                      <p className="mb-3 text-sm text-slate-600">
                        {actionStatus[job.job_id]}
                      </p>
                    )}

                    {job.red_flags && job.red_flags.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-slate-700">
                          Red Flags:
                        </p>
                        {job.red_flags.map((flag, i) => (
                          <div
                            key={i}
                            className={`flex items-start gap-3 rounded-md p-3 ${
                              flag.severity === "high"
                                ? "bg-red-50"
                                : flag.severity === "medium"
                                  ? "bg-amber-50"
                                  : "bg-yellow-50"
                            }`}
                          >
                            <span
                              className={`mt-0.5 shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
                                flag.severity === "high"
                                  ? "bg-red-200 text-red-800"
                                  : flag.severity === "medium"
                                    ? "bg-amber-200 text-amber-800"
                                    : "bg-yellow-200 text-yellow-800"
                              }`}
                            >
                              {flag.severity.toUpperCase()}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium text-slate-800">
                                {flag.code.replace(/_/g, " ")}
                              </p>
                              <p className="text-sm text-slate-600">
                                {flag.description}
                              </p>
                            </div>
                            <span className="shrink-0 text-sm font-bold text-slate-500">
                              +{flag.points}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">
                        No detailed red flags available.
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
