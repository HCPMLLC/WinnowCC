"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";

type Job = {
  id: number;
  company: string;
  company_logo?: string;
  url: string;
  title: string;
  location: string;
  posted_at?: string;
  source: string;
};

type Match = {
  id: number;
  job: Job;
  match_score: number;
  interview_probability?: number | null;
  application_status?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const APPLICATION_STATUSES = ["saved", "applied", "interviewing", "rejected", "offer"] as const;

const STATUS_LABELS: Record<string, string> = {
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  rejected: "Rejected",
  offer: "Offer",
};

const STATUS_COLORS: Record<string, string> = {
  saved: "bg-gray-100 text-gray-700",
  applied: "bg-blue-100 text-blue-700",
  interviewing: "bg-amber-100 text-amber-700",
  rejected: "bg-red-100 text-red-700",
  offer: "bg-green-100 text-green-700",
};

const COLUMN_COLORS: Record<string, string> = {
  saved: "border-t-gray-400",
  applied: "border-t-blue-500",
  interviewing: "border-t-amber-500",
  rejected: "border-t-red-500",
  offer: "border-t-green-500",
};

const FUNNEL_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  saved: { bg: "bg-gray-100", text: "text-gray-700", bar: "bg-gray-400" },
  applied: { bg: "bg-blue-100", text: "text-blue-700", bar: "bg-blue-500" },
  interviewing: { bg: "bg-amber-100", text: "text-amber-700", bar: "bg-amber-500" },
  offer: { bg: "bg-green-100", text: "text-green-700", bar: "bg-green-500" },
};

function ApplicationsPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [allMatches, setAllMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusLoading, setStatusLoading] = useState<number | null>(null);
  const [openDropdown, setOpenDropdown] = useState<number | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Auth guard
  useEffect(() => {
    const guard = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/login", redirectValue));
        return;
      }
      if (!me.onboarding_complete) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/onboarding", redirectValue));
      }
    };
    void guard();
  }, [pathname, router, searchParams]);

  // Load matches
  useEffect(() => {
    const loadMatches = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/matches/all`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error("Failed to load matches.");
        }
        const payload = (await response.json()) as Match[];
        setAllMatches(payload);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load matches.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    void loadMatches();
  }, []);

  // Click-outside to close dropdowns
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpenDropdown(null);
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);

  const handleStatusChange = async (matchId: number, newStatus: string | null) => {
    setStatusLoading(matchId);
    setOpenDropdown(null);
    try {
      const response = await fetch(`${API_BASE}/api/matches/${matchId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus }),
      });
      if (!response.ok) {
        throw new Error("Failed to update application status.");
      }
      const result = (await response.json()) as {
        id: number;
        application_status: string | null;
      };
      setAllMatches((current) =>
        current.map((m) =>
          m.id === matchId
            ? { ...m, application_status: result.application_status }
            : m
        )
      );
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to update status.";
      console.error(message);
    } finally {
      setStatusLoading(null);
    }
  };

  const trackedMatches = allMatches.filter((m) => m.application_status != null);

  const countByStatus = (status: string) =>
    trackedMatches.filter((m) => m.application_status === status).length;

  const matchesForColumn = (status: string) =>
    trackedMatches.filter((m) => m.application_status === status);

  // Funnel stages (forward pipeline, excluding rejected)
  const funnelStages = ["saved", "applied", "interviewing", "offer"] as const;
  const funnelCounts = funnelStages.map((s) => countByStatus(s));
  const rejectedCount = countByStatus("rejected");

  const getTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "1d ago";
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return `${Math.floor(diffDays / 30)}mo ago`;
  };

  if (loading) {
    return (
      <CandidateLayout>
        <div className="animate-pulse">
          <div className="mb-6 h-8 w-48 rounded bg-slate-200"></div>
          <div className="flex gap-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-64 w-72 shrink-0 rounded-lg bg-slate-200"></div>
            ))}
          </div>
        </div>
      </CandidateLayout>
    );
  }

  return (
    <CandidateLayout>
      <CollapsibleTip title="Track Your Applications" defaultOpen={false}>
        <p>
          Drag cards between columns to track your progress. Winnow auto-updates
          status when you apply through the platform.
        </p>
      </CollapsibleTip>

      <header className="mb-6 mt-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Applications</h1>
          <p className="mt-1 text-sm text-slate-600">
            Track your job applications through the pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="/matches"
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            Job Matches
          </a>
          <a
            href="/dashboard"
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            Dashboard
          </a>
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {trackedMatches.length === 0 ? (
        /* Empty state */
        <div className="mt-16 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
            <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-900">No tracked applications yet</h2>
          <p className="mt-2 text-sm text-gray-500">
            Start tracking by setting a status on any job match.
          </p>
          <a
            href="/matches"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            Browse Job Matches
          </a>
        </div>
      ) : (
        <>
          {/* Funnel summary bar */}
          <div className="mb-6 overflow-x-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              {funnelStages.map((stage, i) => {
                const colors = FUNNEL_COLORS[stage];
                const count = funnelCounts[i];
                const prevCount = i > 0 ? funnelCounts[i - 1] : null;
                const conversionPct =
                  prevCount && prevCount > 0
                    ? Math.round((count / prevCount) * 100)
                    : null;

                return (
                  <div key={stage} className="flex items-center gap-3">
                    {i > 0 && (
                      <div className="flex flex-col items-center">
                        <svg className="h-4 w-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                        {conversionPct !== null && (
                          <span className="text-xs text-slate-400">{conversionPct}%</span>
                        )}
                      </div>
                    )}
                    <div className={`rounded-lg ${colors.bg} px-4 py-2 text-center`}>
                      <p className={`text-xl font-bold ${colors.text}`}>{count}</p>
                      <p className={`text-xs font-medium ${colors.text}`}>
                        {STATUS_LABELS[stage]}
                      </p>
                    </div>
                  </div>
                );
              })}
              {/* Rejected - separated */}
              <div className="ml-auto flex items-center gap-2 border-l border-slate-200 pl-4">
                <div className="rounded-lg bg-red-100 px-4 py-2 text-center">
                  <p className="text-xl font-bold text-red-700">{rejectedCount}</p>
                  <p className="text-xs font-medium text-red-700">Rejected</p>
                </div>
              </div>
            </div>
          </div>

          {/* Kanban columns */}
          <div className="flex gap-4 overflow-x-auto pb-4" ref={dropdownRef}>
            {APPLICATION_STATUSES.map((status) => {
              const matches = matchesForColumn(status);
              return (
                <div
                  key={status}
                  className={`w-64 shrink-0 rounded-lg border border-slate-200 border-t-4 bg-slate-50 sm:w-72 ${COLUMN_COLORS[status]}`}
                >
                  {/* Column header */}
                  <div className="flex items-center justify-between px-3 py-2.5">
                    <h3 className="text-sm font-semibold text-slate-700">
                      {STATUS_LABELS[status]}
                    </h3>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status]}`}>
                      {matches.length}
                    </span>
                  </div>

                  {/* Cards */}
                  <div className="max-h-[calc(100vh-320px)] space-y-2 overflow-y-auto px-2 pb-2">
                    {matches.length === 0 && (
                      <p className="px-2 py-4 text-center text-xs text-slate-400">
                        No applications
                      </p>
                    )}
                    {matches.map((match) => (
                      <div
                        key={match.id}
                        className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                      >
                        {/* Title */}
                        <a
                          href="/matches"
                          className="text-sm font-semibold text-slate-900 hover:text-green-700"
                        >
                          {match.job.title}
                        </a>
                        {/* Company */}
                        <p className="mt-0.5 text-xs text-slate-600">
                          {match.job.company}
                        </p>
                        {/* Score + date row */}
                        <div className="mt-2 flex items-center justify-between">
                          <span className="rounded bg-green-600 px-1.5 py-0.5 text-xs font-bold text-white">
                            {match.interview_probability ?? match.match_score}%
                          </span>
                          {match.job.posted_at && (
                            <span className="text-xs text-slate-400">
                              {getTimeAgo(match.job.posted_at)}
                            </span>
                          )}
                        </div>
                        {/* Status dropdown */}
                        <div className="relative mt-2">
                          <button
                            type="button"
                            onClick={() =>
                              setOpenDropdown(
                                openDropdown === match.id ? null : match.id
                              )
                            }
                            disabled={statusLoading === match.id}
                            className={`w-full rounded border px-2 py-1 text-left text-xs font-medium transition-colors ${
                              statusLoading === match.id
                                ? "opacity-50"
                                : "hover:bg-slate-50"
                            } border-slate-200 text-slate-600`}
                          >
                            {statusLoading === match.id
                              ? "Updating..."
                              : `Move to...`}
                            <svg
                              className="float-right mt-0.5 h-3 w-3"
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
                          </button>
                          {openDropdown === match.id && (
                            <div className="absolute left-0 z-20 mt-1 w-full rounded-md border border-slate-200 bg-white py-1 shadow-lg">
                              {APPLICATION_STATUSES.filter(
                                (s) => s !== match.application_status
                              ).map((s) => (
                                <button
                                  key={s}
                                  type="button"
                                  onClick={() =>
                                    handleStatusChange(match.id, s)
                                  }
                                  className="block w-full px-3 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-100"
                                >
                                  {STATUS_LABELS[s]}
                                </button>
                              ))}
                              <div className="my-1 border-t border-slate-100"></div>
                              <button
                                type="button"
                                onClick={() =>
                                  handleStatusChange(match.id, null)
                                }
                                className="block w-full px-3 py-1.5 text-left text-xs text-red-600 hover:bg-red-50"
                              >
                                Remove from tracking
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </CandidateLayout>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense>
      <ApplicationsPageContent />
    </Suspense>
  );
}
