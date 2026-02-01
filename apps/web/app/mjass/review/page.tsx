"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Draft = {
  id: number;
  match_id: number | null;
  job_title: string | null;
  company: string | null;
  location: string | null;
  job_url: string | null;
  status: string;
  application_mode: string;
  created_at: string;
  decided_at: string | null;
};

type DraftDetail = {
  draft: Draft & {
    draft_payload: Record<string, unknown>;
    explain: {
      match_score?: number;
      interview_readiness_score?: number;
      offer_probability?: number;
      matched_skills?: string[];
      missing_skills?: string[];
      [key: string]: unknown;
    };
  };
  events: Array<{
    id: number;
    event_type: string;
    actor_type: string;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
};

export default function MJASSReviewPage() {
  const router = useRouter();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<DraftDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState(false);
  const [filter, setFilter] = useState<string>("all");

  const loadDrafts = async () => {
    try {
      setError(null);
      const url = filter === "all"
        ? `${API_BASE}/api/mjass/drafts`
        : `${API_BASE}/api/mjass/drafts?status=${filter}`;
      const response = await fetch(url, {
        credentials: "include",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (!response.ok) throw new Error("Failed to load drafts");
      const data = await response.json();
      setDrafts(data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDrafts();
  }, [filter]);

  const loadDraftDetail = async (draftId: number) => {
    try {
      const response = await fetch(`${API_BASE}/api/mjass/drafts/${draftId}`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to load draft details");
      const data = (await response.json()) as DraftDetail;
      setSelectedDraft(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load draft");
    }
  };

  const handleDecision = async (decision: "approve" | "reject" | "request_changes", note?: string) => {
    if (!selectedDraft) return;
    setDeciding(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/mjass/drafts/${selectedDraft.draft.id}/decision`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ decision, note }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to submit decision");
      }
      // Reload drafts and close detail
      await loadDrafts();
      setSelectedDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit decision");
    } finally {
      setDeciding(false);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "draft": return "bg-slate-100 text-slate-700";
      case "approved": return "bg-emerald-100 text-emerald-700";
      case "rejected": return "bg-red-100 text-red-700";
      case "changes_requested": return "bg-amber-100 text-amber-700";
      case "submitted": return "bg-blue-100 text-blue-700";
      default: return "bg-slate-100 text-slate-700";
    }
  };

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center">
        <p className="text-sm text-slate-500">Loading...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Application Drafts</h1>
        <p className="text-sm text-slate-600">
          Review and approve application drafts before submission.
        </p>
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            onClick={() => router.push("/matches")}
            className="rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700"
          >
            Back to Matches
          </button>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-full border border-slate-300 px-3 py-2 text-xs"
          >
            <option value="all">All Drafts</option>
            <option value="draft">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="changes_requested">Changes Requested</option>
          </select>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
          <button
            type="button"
            onClick={() => setError(null)}
            className="ml-2 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Draft List */}
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">
            Drafts ({drafts.length})
          </h2>
          {drafts.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
              No drafts found. Create one from the Matches page.
            </div>
          ) : (
            drafts.map((draft) => (
              <button
                key={draft.id}
                type="button"
                onClick={() => loadDraftDetail(draft.id)}
                className={`rounded-2xl border p-4 text-left transition ${
                  selectedDraft?.draft.id === draft.id
                    ? "border-blue-500 bg-blue-50"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-slate-900">
                      {draft.job_title || "Untitled"}
                    </div>
                    <div className="text-sm text-slate-600">
                      {draft.company} - {draft.location}
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(draft.status)}`}
                  >
                    {draft.status.replace("_", " ")}
                  </span>
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  Created {new Date(draft.created_at).toLocaleDateString()}
                  {draft.decided_at && (
                    <> - Decided {new Date(draft.decided_at).toLocaleDateString()}</>
                  )}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Draft Detail */}
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">
            Details
          </h2>
          {selectedDraft ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">
                    {selectedDraft.draft.job_title}
                  </h3>
                  <p className="text-sm text-slate-600">
                    {selectedDraft.draft.company} - {selectedDraft.draft.location}
                  </p>
                  {selectedDraft.draft.job_url && (
                    <a
                      href={selectedDraft.draft.job_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 text-xs text-blue-600 underline"
                    >
                      View job posting
                    </a>
                  )}
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${statusColor(selectedDraft.draft.status)}`}
                >
                  {selectedDraft.draft.status.replace("_", " ")}
                </span>
              </div>

              {/* Explainability */}
              {selectedDraft.draft.explain && (
                <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">
                    Why You Matched
                  </h4>
                  <div className="mt-3 flex gap-3">
                    {selectedDraft.draft.explain.match_score !== undefined && (
                      <div className="rounded-lg bg-emerald-100 px-3 py-2 text-center">
                        <div className="text-lg font-bold text-emerald-700">
                          {selectedDraft.draft.explain.match_score}
                        </div>
                        <div className="text-xs text-emerald-600">Match</div>
                      </div>
                    )}
                    {selectedDraft.draft.explain.interview_readiness_score !== undefined && (
                      <div className="rounded-lg bg-blue-100 px-3 py-2 text-center">
                        <div className="text-lg font-bold text-blue-700">
                          {selectedDraft.draft.explain.interview_readiness_score}
                        </div>
                        <div className="text-xs text-blue-600">Interview</div>
                      </div>
                    )}
                    {selectedDraft.draft.explain.offer_probability !== undefined && (
                      <div className="rounded-lg bg-purple-100 px-3 py-2 text-center">
                        <div className="text-lg font-bold text-purple-700">
                          {selectedDraft.draft.explain.offer_probability}
                        </div>
                        <div className="text-xs text-purple-600">Offer %</div>
                      </div>
                    )}
                  </div>

                  {selectedDraft.draft.explain.matched_skills &&
                   selectedDraft.draft.explain.matched_skills.length > 0 && (
                    <div className="mt-3">
                      <div className="text-xs text-slate-500">Matched Skills:</div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {selectedDraft.draft.explain.matched_skills.map((skill, i) => (
                          <span
                            key={i}
                            className="rounded-full bg-emerald-200 px-2 py-0.5 text-xs text-emerald-800"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Event History */}
              {selectedDraft.events.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">
                    History
                  </h4>
                  <div className="mt-2 flex flex-col gap-2">
                    {selectedDraft.events.map((event) => (
                      <div
                        key={event.id}
                        className="flex items-center gap-2 text-xs text-slate-600"
                      >
                        <span className="rounded bg-slate-100 px-2 py-0.5">
                          {event.event_type}
                        </span>
                        <span>by {event.actor_type}</span>
                        <span className="text-slate-400">
                          {new Date(event.created_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Decision Buttons */}
              {selectedDraft.draft.status === "draft" && (
                <div className="mt-6 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                  <button
                    type="button"
                    onClick={() => handleDecision("approve")}
                    disabled={deciding}
                    className="rounded-full bg-emerald-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    {deciding ? "..." : "Approve"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDecision("reject")}
                    disabled={deciding}
                    className="rounded-full bg-red-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    {deciding ? "..." : "Reject"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDecision("request_changes", "Needs revision")}
                    disabled={deciding}
                    className="rounded-full bg-amber-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    {deciding ? "..." : "Request Changes"}
                  </button>
                </div>
              )}

              {selectedDraft.draft.status !== "draft" && (
                <div className="mt-6 border-t border-slate-100 pt-4 text-sm text-slate-500">
                  This draft has been {selectedDraft.draft.status.replace("_", " ")}.
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
              Select a draft to view details
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
