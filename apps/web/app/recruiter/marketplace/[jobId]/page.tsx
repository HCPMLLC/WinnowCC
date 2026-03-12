"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { parseApiError } from "../../../lib/api-error";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface MarketplaceJobDetail {
  id: number;
  title: string;
  company: string | null;
  location: string | null;
  remote_flag: boolean | null;
  salary_min: number | null;
  salary_max: number | null;
  currency: string | null;
  source: string | null;
  url: string | null;
  description_text: string | null;
  posted_at: string | null;
  cached_candidates_count: number;
  cache_fresh: boolean;
}

interface CandidateMatch {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  matched_skills: string[];
  match_score: number;
  profile_visibility: string;
  in_pipeline: boolean;
}

interface CandidatesResponse {
  job_id: number;
  job_title: string;
  candidates: CandidateMatch[];
  total_cached: number;
  needs_refresh: boolean;
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-700 bg-emerald-50";
  if (score >= 50) return "text-amber-700 bg-amber-50";
  return "text-slate-600 bg-slate-100";
}

export default function MarketplaceJobDetailPage() {
  const params = useParams();
  const jobId = params.jobId as string;

  const [job, setJob] = useState<MarketplaceJobDetail | null>(null);
  const [candidates, setCandidates] = useState<CandidateMatch[]>([]);
  const [totalCached, setTotalCached] = useState(0);
  const [needsRefresh, setNeedsRefresh] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [refreshing, setRefreshing] = useState(false);
  const [refreshPercent, setRefreshPercent] = useState(0);
  const [refreshMessage, setRefreshMessage] = useState("");

  const [addedToPipeline, setAddedToPipeline] = useState<Set<number>>(new Set());
  const [addingId, setAddingId] = useState<number | null>(null);
  const [pipelineError, setPipelineError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/recruiter/marketplace/jobs/${jobId}`, {
        credentials: "include",
      }).then((r) => r.json()),
      fetch(`${API_BASE}/api/recruiter/marketplace/jobs/${jobId}/candidates?limit=50`, {
        credentials: "include",
      }).then((r) => r.json()),
    ])
      .then(([jobData, candData]: [MarketplaceJobDetail, CandidatesResponse]) => {
        setJob(jobData);
        setCandidates(candData.candidates || []);
        setTotalCached(candData.total_cached || 0);
        setNeedsRefresh(candData.needs_refresh ?? true);
        const pipelined = new Set(
          (candData.candidates || []).filter((c) => c.in_pipeline).map((c) => c.id),
        );
        setAddedToPipeline(pipelined);
      })
      .catch((err) => setError(err.message || "Failed to load job"))
      .finally(() => setLoading(false));
  }, [jobId]);

  async function handleRefreshCandidates() {
    setRefreshing(true);
    setRefreshPercent(0);
    setRefreshMessage("Starting...");
    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/marketplace/jobs/${jobId}/refresh-candidates`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok || !res.body) {
        setRefreshMessage("Refresh failed");
        setRefreshing(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              setRefreshPercent(event.percent || 0);
              setRefreshMessage(event.message || "");
            } catch {
              // ignore
            }
          }
        }
      }

      // Reload candidates
      const candRes = await fetch(
        `${API_BASE}/api/recruiter/marketplace/jobs/${jobId}/candidates?limit=50`,
        { credentials: "include" },
      );
      if (candRes.ok) {
        const data: CandidatesResponse = await candRes.json();
        setCandidates(data.candidates);
        setTotalCached(data.total_cached);
        setNeedsRefresh(false);
        const pipelined = new Set(
          data.candidates.filter((c) => c.in_pipeline).map((c) => c.id),
        );
        setAddedToPipeline(pipelined);
      }
    } catch (err) {
      console.error("Refresh failed:", err);
      setRefreshMessage("Refresh failed");
    } finally {
      setRefreshing(false);
      setRefreshPercent(0);
      setRefreshMessage("");
    }
  }

  async function handleAddToPipeline(candidate: CandidateMatch) {
    setAddingId(candidate.id);
    setPipelineError("");
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/pipeline`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_profile_id: candidate.id,
          source: "marketplace-match",
          stage: "sourced",
          match_score: candidate.match_score,
        }),
      });
      if (res.ok) {
        setAddedToPipeline((prev) => new Set(prev).add(candidate.id));
      } else if (res.status === 429) {
        const data = await res.json();
        setPipelineError(parseApiError(data, "Pipeline limit reached."));
      } else {
        const data = await res.json();
        setPipelineError(parseApiError(data, "Failed to add to pipeline"));
      }
    } catch {
      setPipelineError("Network error");
    } finally {
      setAddingId(null);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-sm text-slate-500">Loading job...</div>;
  }
  if (error || !job) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-red-600">{error || "Job not found"}</p>
        <Link href="/recruiter/marketplace" className="mt-2 inline-block text-sm text-slate-600 hover:underline">
          Back to Marketplace
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/recruiter/marketplace"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
        Back to Marketplace
      </Link>

      {/* Job Detail Card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{job.title}</h1>
            <p className="mt-1 text-sm text-slate-600">
              {job.company || "Unknown Company"}
              {job.location && ` \u00b7 ${job.location}`}
              {job.remote_flag && (
                <span className="ml-2 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                  Remote
                </span>
              )}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            {job.source && (
              <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                {job.source}
              </span>
            )}
            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline"
              >
                View original
              </a>
            )}
          </div>
        </div>

        {/* Metadata row */}
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
          {(job.salary_min || job.salary_max) && (
            <span>
              Salary: {job.salary_min ? `$${job.salary_min.toLocaleString()}` : ""}
              {job.salary_min && job.salary_max ? " - " : ""}
              {job.salary_max ? `$${job.salary_max.toLocaleString()}` : ""}{" "}
              {job.currency || "USD"}
            </span>
          )}
          {job.posted_at && (
            <span>Posted: {new Date(job.posted_at).toLocaleDateString()}</span>
          )}
        </div>

        {/* Description */}
        {job.description_text && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-slate-700">Description</h3>
            <p className="mt-1 whitespace-pre-line text-sm text-slate-600 max-h-60 overflow-y-auto">
              {job.description_text}
            </p>
          </div>
        )}
      </div>

      {/* Candidates Section */}
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            Matching Candidates
            {totalCached > 0 && (
              <span className="ml-2 text-sm font-normal text-slate-500">
                ({totalCached} found)
              </span>
            )}
          </h2>
          <button
            onClick={handleRefreshCandidates}
            disabled={refreshing}
            className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {refreshing ? "Scanning..." : needsRefresh ? "Find Matching Candidates" : "Refresh Matches"}
          </button>
        </div>

        {/* Progress bar */}
        {refreshing && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>{refreshMessage}</span>
              <span>{refreshPercent}%</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-slate-700 transition-all duration-300"
                style={{ width: `${refreshPercent}%` }}
              />
            </div>
          </div>
        )}

        {pipelineError && (
          <div className="mt-3 rounded-md bg-red-50 p-2 text-xs text-red-600">
            {pipelineError}
          </div>
        )}

        {/* Candidates list */}
        {candidates.length === 0 && !refreshing ? (
          <div className="mt-6 py-8 text-center text-sm text-slate-400">
            {needsRefresh
              ? 'Click "Find Matching Candidates" to scan your pipeline.'
              : "No matching candidates found for this job."}
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {candidates.map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-4 rounded-lg border border-slate-100 px-4 py-3 hover:bg-slate-50"
              >
                {/* Score badge */}
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold ${scoreColor(c.match_score)}`}
                >
                  {Math.round(c.match_score)}
                </div>

                {/* Candidate info */}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900 truncate">{c.name}</p>
                  {c.headline && (
                    <p className="text-xs text-slate-500 truncate">{c.headline}</p>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.matched_skills.slice(0, 5).map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Location + years */}
                <div className="hidden sm:block text-right text-xs text-slate-500 shrink-0">
                  {c.location && <p>{c.location}</p>}
                  {c.years_experience != null && <p>{c.years_experience} yrs exp</p>}
                </div>

                {/* Add to pipeline button */}
                <div className="shrink-0">
                  {addedToPipeline.has(c.id) || c.in_pipeline ? (
                    <span className="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
                      In Pipeline
                    </span>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        handleAddToPipeline(c);
                      }}
                      disabled={addingId === c.id}
                      className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {addingId === c.id ? "Adding..." : "+ Pipeline"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
