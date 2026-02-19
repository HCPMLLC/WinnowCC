"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useProgress } from "../../../hooks/useProgress";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface JobDetail {
  id: number;
  title: string;
  description: string;
  requirements: string | null;
  nice_to_haves: string | null;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  status: string;
  application_url: string | null;
  application_email: string | null;
  view_count: number;
  application_count: number;
  posted_at: string | null;
  closes_at: string | null;
  created_at: string;
  updated_at: string | null;
  // Enhanced fields
  job_id_external: string | null;
  start_date: string | null;
  close_date: string | null;
  job_category: string | null;
  department: string | null;
  certifications_required: string[] | null;
  job_type: string | null;
  // Archival
  archived: boolean;
  archived_at: string | null;
  archived_reason: string | null;
  // Document parsing
  parsed_from_document: boolean;
  parsing_confidence: number | null;
}

interface TopCandidate {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  matched_skills: string[];
  match_score: number;
  profile_visibility: string;
}

interface Distribution {
  id: number;
  employer_job_id: number;
  board_connection_id: number;
  external_job_id: string | null;
  status: string;
  submitted_at: string | null;
  live_at: string | null;
  removed_at: string | null;
  error_message: string | null;
  impressions: number;
  clicks: number;
  applications: number;
  cost_spent: number;
  board_type: string | null;
  board_name: string | null;
}

const DIST_STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  submitted: "bg-blue-100 text-blue-800",
  live: "bg-emerald-100 text-emerald-800",
  expired: "bg-slate-100 text-slate-600",
  failed: "bg-red-100 text-red-800",
  removed: "bg-slate-100 text-slate-500",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800",
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  closed: "bg-red-100 text-red-800",
};

function containsHtml(text: string): boolean {
  return /<\/?[a-z][\s\S]*>/i.test(text);
}

function RichText({ text }: { text: string }) {
  if (containsHtml(text)) {
    return (
      <div
        className="prose prose-sm max-w-none text-slate-600"
        dangerouslySetInnerHTML={{ __html: text }}
      />
    );
  }
  return (
    <p className="whitespace-pre-wrap text-sm text-slate-600">{text}</p>
  );
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const action = useProgress();
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [distributions, setDistributions] = useState<Distribution[]>([]);
  const dist = useProgress();
  const [activeDist, setActiveDist] = useState<string | null>(null);
  const [topCandidates, setTopCandidates] = useState<TopCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [totalEvaluated, setTotalEvaluated] = useState(0);

  async function fetchTopCandidates(id: string) {
    setCandidatesLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${id}/top-candidates?limit=5`,
        { credentials: "include" },
      );
      if (res.ok) {
        const data = await res.json();
        setTopCandidates(data.candidates || []);
        setTotalEvaluated(data.total_evaluated || 0);
      }
    } catch (err) {
      console.error("Failed to fetch top candidates:", err);
    } finally {
      setCandidatesLoading(false);
    }
  }

  async function fetchDistributions(id: string) {
    try {
      const res = await fetch(
        `${API_BASE}/api/distribution/jobs/${id}/status`,
        { credentials: "include" },
      );
      if (res.ok) {
        const data = await res.json();
        setDistributions(data.distributions || []);
      }
    } catch (err) {
      console.error("Failed to fetch distributions:", err);
    }
  }

  useEffect(() => {
    async function fetchJob() {
      try {
        const res = await fetch(`${API_BASE}/api/employer/jobs/${jobId}`, {
          credentials: "include",
        });
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || "Job not found");
        }
        const jobData = await res.json();
        setJob(jobData);
        fetchDistributions(jobId);
        if (jobData.status === "active") {
          fetchTopCandidates(jobId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
      } finally {
        setIsLoading(false);
      }
    }
    fetchJob();
  }, [jobId]);

  async function updateStatus(newStatus: string) {
    if (!job) return;
    setActiveAction(newStatus);
    action.start();
    try {
      const res = await fetch(`${API_BASE}/api/employer/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to update status");
      }
      setJob(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      action.complete();
      setTimeout(() => setActiveAction(null), 400);
    }
  }

  async function archiveJob() {
    if (!job) return;
    setActiveAction("archive");
    action.start();
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${job.id}/archive`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to archive");
      }
      const updated = await fetch(
        `${API_BASE}/api/employer/jobs/${job.id}`,
        { credentials: "include" },
      );
      if (updated.ok) setJob(await updated.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Archive failed");
    } finally {
      action.complete();
      setTimeout(() => setActiveAction(null), 400);
    }
  }

  async function unarchiveJob() {
    if (!job) return;
    setActiveAction("unarchive");
    action.start();
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${job.id}/unarchive`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to unarchive");
      }
      const updated = await fetch(
        `${API_BASE}/api/employer/jobs/${job.id}`,
        { credentials: "include" },
      );
      if (updated.ok) setJob(await updated.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unarchive failed");
    } finally {
      action.complete();
      setTimeout(() => setActiveAction(null), 400);
    }
  }

  async function distributeJob() {
    if (!job) return;
    setActiveDist("distribute");
    dist.start();
    try {
      const res = await fetch(
        `${API_BASE}/api/distribution/jobs/${job.id}/distribute`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
          credentials: "include",
        },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Distribution failed");
      }
      fetchDistributions(String(job.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Distribution failed");
    } finally {
      dist.complete();
      setTimeout(() => setActiveDist(null), 400);
    }
  }

  async function removeFromBoards() {
    if (!job || !confirm("Remove this job from all boards?")) return;
    setActiveDist("remove");
    dist.start();
    try {
      const res = await fetch(
        `${API_BASE}/api/distribution/jobs/${job.id}/remove`,
        { method: "POST", credentials: "include" },
      );
      if (res.ok) {
        fetchDistributions(String(job.id));
      }
    } catch (err) {
      console.error("Remove failed:", err);
    } finally {
      dist.complete();
      setTimeout(() => setActiveDist(null), 400);
    }
  }

  async function deleteJob() {
    if (!job || !confirm("Are you sure you want to delete this job?")) return;
    setActiveAction("delete");
    action.start();
    try {
      const res = await fetch(`${API_BASE}/api/employer/jobs/${job.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok && res.status !== 204) {
        throw new Error("Failed to delete job");
      }
      router.push("/employer/jobs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      action.complete();
      setTimeout(() => setActiveAction(null), 400);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
        <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />
      </div>
    );
  }

  if (error && !job) {
    return (
      <div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
        <Link
          href="/employer/jobs"
          className="mt-4 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          &larr; Back to Jobs
        </Link>
      </div>
    );
  }

  if (!job) return null;

  return (
    <div>
      {/* Archived Banner */}
      {job.archived && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          This job was archived
          {job.archived_reason ? ` (${job.archived_reason})` : ""}
          {job.archived_at &&
            ` on ${new Date(job.archived_at).toLocaleDateString()}`}
          .
          <button
            onClick={unarchiveJob}
            disabled={action.isActive}
            className="ml-2 font-medium underline hover:text-amber-900"
          >
            {activeAction === "unarchive"
              ? `Unarchiving... ${action.pct}%`
              : "Unarchive"}
          </button>
        </div>
      )}

      {/* Parsed from document badge */}
      {job.parsed_from_document && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          Parsed from uploaded document
          {job.parsing_confidence != null &&
            ` (${(job.parsing_confidence * 100).toFixed(0)}% confidence)`}
          .{" "}
          <Link
            href={`/employer/jobs/${job.id}/edit`}
            className="font-medium underline hover:text-blue-900"
          >
            Review and edit fields
          </Link>{" "}
          before publishing.
        </div>
      )}

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link
            href="/employer/jobs"
            className="mb-2 inline-block text-sm text-slate-500 hover:text-slate-700"
          >
            &larr; Back to Jobs
          </Link>
          <p className="mb-1 text-sm font-medium text-slate-400">
            Job ID: {job.job_id_external || job.id}
          </p>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-slate-900">{job.title}</h1>
            {job.department && (
              <span className="text-lg text-slate-500">— {job.department}</span>
            )}
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}
            >
              {job.status}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="mb-6 flex flex-wrap gap-3">
        {!job.archived && (
          <Link
            href={`/employer/jobs/${job.id}/edit`}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Edit Details
          </Link>
        )}
        {!job.archived && job.status === "draft" && (
          <button
            onClick={() => updateStatus("active")}
            disabled={action.isActive}
            className="relative overflow-hidden rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "active" && (
              <span className="absolute inset-y-0 left-0 bg-emerald-500 transition-all duration-200" style={{ width: `${action.progress}%` }} />
            )}
            <span className="relative">
              {activeAction === "active" ? `Publishing... ${action.pct}%` : "Publish"}
            </span>
          </button>
        )}
        {!job.archived && job.status === "active" && (
          <button
            onClick={() => updateStatus("paused")}
            disabled={action.isActive}
            className="relative overflow-hidden rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "paused" && (
              <span className="absolute inset-y-0 left-0 bg-amber-500 transition-all duration-200" style={{ width: `${action.progress}%` }} />
            )}
            <span className="relative">
              {activeAction === "paused" ? `Pausing... ${action.pct}%` : "Pause"}
            </span>
          </button>
        )}
        {!job.archived && job.status === "paused" && (
          <button
            onClick={() => updateStatus("active")}
            disabled={action.isActive}
            className="relative overflow-hidden rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "active" && (
              <span className="absolute inset-y-0 left-0 bg-emerald-500 transition-all duration-200" style={{ width: `${action.progress}%` }} />
            )}
            <span className="relative">
              {activeAction === "active" ? `Resuming... ${action.pct}%` : "Resume"}
            </span>
          </button>
        )}
        {!job.archived && job.status !== "closed" && (
          <button
            onClick={() => updateStatus("closed")}
            disabled={action.isActive}
            className="relative overflow-hidden rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "closed" && (
              <span className="absolute inset-y-0 left-0 bg-slate-100 transition-all duration-200" style={{ width: `${action.progress}%` }} />
            )}
            <span className="relative">
              {activeAction === "closed" ? `Closing... ${action.pct}%` : "Close"}
            </span>
          </button>
        )}
        {!job.archived && (
          <button
            onClick={archiveJob}
            disabled={action.isActive}
            className="relative overflow-hidden rounded-md border border-orange-300 px-4 py-2 text-sm font-medium text-orange-600 hover:bg-orange-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "archive" && (
              <span className="absolute inset-y-0 left-0 bg-orange-100 transition-all duration-200" style={{ width: `${action.progress}%` }} />
            )}
            <span className="relative">
              {activeAction === "archive" ? `Archiving... ${action.pct}%` : "Archive"}
            </span>
          </button>
        )}
        {job.archived && (
          <button
            onClick={unarchiveJob}
            disabled={action.isActive}
            className="relative overflow-hidden rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "unarchive" && (
              <span className="absolute inset-y-0 left-0 bg-slate-600 transition-all duration-200" style={{ width: `${action.progress}%` }} />
            )}
            <span className="relative">
              {activeAction === "unarchive" ? `Unarchiving... ${action.pct}%` : "Unarchive"}
            </span>
          </button>
        )}
        <button
          onClick={deleteJob}
          disabled={action.isActive}
          className="relative overflow-hidden rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {activeAction === "delete" && (
            <span className="absolute inset-y-0 left-0 bg-red-100 transition-all duration-200" style={{ width: `${action.progress}%` }} />
          )}
          <span className="relative">
            {activeAction === "delete" ? `Deleting... ${action.pct}%` : "Delete"}
          </span>
        </button>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Views</p>
          <p className="text-2xl font-bold text-slate-900">{job.view_count}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Applications</p>
          <p className="text-2xl font-bold text-slate-900">
            {job.application_count}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Posted</p>
          <p className="text-sm font-medium text-slate-900">
            {job.posted_at
              ? new Date(job.posted_at).toLocaleDateString()
              : "Not published"}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Created</p>
          <p className="text-sm font-medium text-slate-900">
            {new Date(job.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Distribution Status */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            Board Distribution
          </h2>
          <div className="flex gap-2">
            {job.status === "active" && !job.archived && (
              <button
                onClick={distributeJob}
                disabled={dist.isActive}
                className="relative overflow-hidden rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {activeDist === "distribute" && (
                  <span className="absolute inset-y-0 left-0 bg-slate-700 transition-all duration-200" style={{ width: `${dist.progress}%` }} />
                )}
                <span className="relative">
                  {activeDist === "distribute" ? `Distributing... ${dist.pct}%` : "Distribute to Boards"}
                </span>
              </button>
            )}
            {distributions.some(
              (d) => d.status === "live" || d.status === "pending",
            ) && (
              <button
                onClick={removeFromBoards}
                disabled={dist.isActive}
                className="relative overflow-hidden rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {activeDist === "remove" && (
                  <span className="absolute inset-y-0 left-0 bg-red-100 transition-all duration-200" style={{ width: `${dist.progress}%` }} />
                )}
                <span className="relative">
                  {activeDist === "remove" ? `Removing... ${dist.pct}%` : "Remove from All"}
                </span>
              </button>
            )}
          </div>
        </div>

        {distributions.length === 0 ? (
          <p className="text-sm text-slate-500">
            Not distributed to any boards yet.
            {job.status === "active" &&
              " Click \"Distribute to Boards\" to push this job to your connected boards."}
          </p>
        ) : (
          <div className="space-y-3">
            {distributions.map((dist) => (
              <div
                key={dist.id}
                className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-slate-900">
                    {dist.board_name || dist.board_type}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      DIST_STATUS_COLORS[dist.status] ??
                      "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {dist.status}
                  </span>
                  {dist.error_message && (
                    <span
                      className="text-xs text-red-600 truncate max-w-xs"
                      title={dist.error_message}
                    >
                      {dist.error_message}
                    </span>
                  )}
                </div>
                <div className="flex gap-6 text-xs text-slate-500">
                  <span>{dist.impressions.toLocaleString()} impressions</span>
                  <span>{dist.clicks.toLocaleString()} clicks</span>
                  <span>{dist.applications.toLocaleString()} applications</span>
                  {dist.cost_spent > 0 && (
                    <span>${dist.cost_spent.toFixed(2)} spent</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top Matched Candidates */}
      {job.status === "active" && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              Top Matched Candidates
            </h2>
            <Link
              href="/employer/candidates"
              className="text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              Search All Candidates &rarr;
            </Link>
          </div>

          {candidatesLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-20 animate-pulse rounded-lg bg-slate-100"
                />
              ))}
            </div>
          ) : topCandidates.length === 0 ? (
            <p className="text-sm text-slate-500">
              No matching candidates found.
              {totalEvaluated === 0
                ? " There are no candidates in the system yet."
                : ` Evaluated ${totalEvaluated} candidate(s) but none scored above the threshold.`}
            </p>
          ) : (
            <div className="space-y-3">
              {topCandidates.map((candidate) => (
                <div
                  key={candidate.id}
                  className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/employer/candidates/${candidate.id}`}
                        className="text-sm font-semibold text-slate-900 hover:text-blue-600"
                      >
                        {candidate.name}
                      </Link>
                      {candidate.profile_visibility === "anonymous" && (
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                          Anonymous
                        </span>
                      )}
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
                        {candidate.match_score}%
                      </span>
                    </div>
                    {candidate.headline && (
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        {candidate.headline}
                      </p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      {candidate.location && (
                        <span>{candidate.location}</span>
                      )}
                      {candidate.years_experience != null && (
                        <span>
                          {candidate.years_experience}+ yrs exp
                        </span>
                      )}
                    </div>
                    {candidate.matched_skills.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {candidate.matched_skills.slice(0, 6).map((skill) => (
                          <span
                            key={skill}
                            className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800"
                          >
                            {skill}
                          </span>
                        ))}
                        {candidate.matched_skills.length > 6 && (
                          <span className="text-[11px] text-slate-400">
                            +{candidate.matched_skills.length - 6} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <Link
                    href={`/employer/candidates/${candidate.id}`}
                    className="ml-4 shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                  >
                    View Profile
                  </Link>
                </div>
              ))}
              {totalEvaluated > 0 && (
                <p className="pt-1 text-xs text-slate-400">
                  Showing top {topCandidates.length} of {totalEvaluated} evaluated candidate(s)
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Details — mirrors Job Edit Posting layout */}
      <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        {/* Job fields table — 4 columns */}
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left">
              <th className="pb-2 pr-4 font-medium text-slate-700">Field</th>
              <th className="pb-2 pr-4 font-medium text-slate-700">Value</th>
              <th className="pb-2 pr-4 font-medium text-slate-700">Field</th>
              <th className="pb-2 font-medium text-slate-700">Value</th>
            </tr>
          </thead>
          <tbody className="text-slate-600">
            <tr className="border-b border-slate-100">
              <td className="py-2 pr-4 font-medium text-slate-700">Job ID</td>
              <td className="py-2 pr-4">{job.job_id_external || job.id}</td>
              <td className="py-2 pr-4 font-medium text-slate-700">Job Type</td>
              <td className="py-2 capitalize">{job.job_type || "—"}</td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 pr-4 font-medium text-slate-700">Job Category</td>
              <td className="py-2 pr-4">{job.job_category || "—"}</td>
              <td className="py-2 pr-4 font-medium text-slate-700">Location</td>
              <td className="py-2">{job.location || "—"}</td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 pr-4 font-medium text-slate-700">Remote Policy</td>
              <td className="py-2 pr-4 capitalize">{job.remote_policy || "—"}</td>
              <td className="py-2 pr-4 font-medium text-slate-700">Start Date</td>
              <td className="py-2">
                {job.start_date
                  ? new Date(job.start_date + "T00:00:00").toLocaleDateString()
                  : "—"}
              </td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 pr-4 font-medium text-slate-700">Application Deadline</td>
              <td className="py-2 pr-4">
                {job.close_date
                  ? new Date(job.close_date + "T00:00:00").toLocaleDateString()
                  : "—"}
              </td>
              <td className="py-2 pr-4 font-medium text-slate-700">Employment Type</td>
              <td className="py-2 capitalize">{job.employment_type || "—"}</td>
            </tr>
            <tr>
              <td className="py-2 pr-4 font-medium text-slate-700">Salary Min (USD)</td>
              <td className="py-2 pr-4">
                {job.salary_min != null
                  ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(job.salary_min)
                  : "—"}
              </td>
              <td className="py-2 pr-4 font-medium text-slate-700">Salary Max (USD)</td>
              <td className="py-2">
                {job.salary_max != null
                  ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(job.salary_max)
                  : "—"}
              </td>
            </tr>
          </tbody>
        </table>

        {/* Description */}
        <div>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            Description
          </h2>
          <RichText text={job.description} />
        </div>

        {/* Minimum Required Experience */}
        {job.requirements && (
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">
              Minimum Required Experience
            </h2>
            <RichText text={job.requirements} />
          </div>
        )}

        {/* Preferred Experience */}
        {job.nice_to_haves && (
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">
              Preferred Experience
            </h2>
            <RichText text={job.nice_to_haves} />
          </div>
        )}

        {/* Row: Application Email + URL */}
        {(job.application_email || job.application_url) && (
          <div className="grid grid-cols-1 gap-6 text-sm md:grid-cols-2">
            <div>
              <span className="font-medium text-slate-700">Application Email</span>
              <p className="mt-0.5 text-slate-600">{job.application_email || "—"}</p>
            </div>
            <div>
              <span className="font-medium text-slate-700">Application URL</span>
              <p className="mt-0.5 text-slate-600">
                {job.application_url ? (
                  <a href={job.application_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    {job.application_url}
                  </a>
                ) : "—"}
              </p>
            </div>
          </div>
        )}

        {/* Certifications */}
        {job.certifications_required &&
          job.certifications_required.length > 0 && (
            <div>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">
                Required Certifications
              </h2>
              <div className="flex flex-wrap gap-2">
                {job.certifications_required.map((cert, i) => (
                  <span
                    key={i}
                    className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700"
                  >
                    {cert}
                  </span>
                ))}
              </div>
            </div>
          )}
      </div>
    </div>
  );
}
