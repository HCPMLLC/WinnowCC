"use client";

import { useEffect, useState } from "react";
import { parseApiError } from "../lib/api-error";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface RecruiterJob {
  id: number;
  title: string;
  client_company_name: string | null;
}

interface IntroUsage {
  used: number;
  limit: number;
  tier: string;
}

interface Props {
  candidateProfileId: number;
  candidateName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function IntroductionRequestModal({
  candidateProfileId,
  candidateName,
  onClose,
  onSuccess,
}: Props) {
  const [jobs, setJobs] = useState<RecruiterJob[]>([]);
  const [usage, setUsage] = useState<IntroUsage | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // Load recruiter's jobs for optional job selector
    fetch(`${API_BASE}/api/recruiter/jobs?limit=100`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        const list = Array.isArray(data) ? data : data.jobs || [];
        setJobs(list);
      })
      .catch(() => {});

    // Load usage
    fetch(`${API_BASE}/api/recruiter/introduction-usage`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setUsage(data);
      })
      .catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (message.length < 20) {
      setError("Message must be at least 20 characters.");
      return;
    }
    setSubmitting(true);
    setError("");

    const body: Record<string, unknown> = {
      candidate_profile_id: candidateProfileId,
      message,
    };
    if (selectedJobId) body.recruiter_job_id = Number(selectedJobId);

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/introductions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        onSuccess();
      } else {
        const data = await res.json();
        setError(parseApiError(data, "Failed to send introduction request."));
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const remaining = usage ? usage.limit - usage.used : null;
  const isUnlimited = usage && usage.limit >= 999;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="mx-4 w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            Request Introduction
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="mb-4 text-sm text-slate-600">
          Send a message to <span className="font-medium text-slate-900">{candidateName}</span>.
          If they accept, their contact information will be shared with you.
        </p>

        {usage && !isUnlimited && (
          <div className="mb-4 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span className="font-medium">{usage.used}</span> of{" "}
            <span className="font-medium">{usage.limit}</span> intro requests used this month
            {remaining !== null && remaining <= 5 && remaining > 0 && (
              <span className="ml-1 text-amber-600">({remaining} remaining)</span>
            )}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {jobs.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Related Job (optional)
              </label>
              <select
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">None</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title}{j.client_company_name ? ` (${j.client_company_name})` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Message <span className="text-slate-400">(min 20 chars)</span>
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              maxLength={1000}
              placeholder="Introduce yourself and explain why you'd like to connect..."
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
            <div className="mt-1 text-right text-xs text-slate-400">
              {message.length}/1000
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || message.length < 20}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {submitting ? "Sending..." : "Send Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
