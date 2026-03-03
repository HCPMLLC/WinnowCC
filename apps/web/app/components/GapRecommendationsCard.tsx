"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Resource = {
  type: string;
  name: string;
  provider: string;
  url_hint: string;
  estimated_hours: number;
  cost: string;
};

type Gap = {
  skill: string;
  priority?: string;
  time_estimate: string;
  resources: Resource[];
  quick_win: string;
  portfolio_project?: string;
};

type OverallPlan = {
  recommended_order: string[];
  total_time_estimate: string;
  strategy: string;
};

type Recommendations = {
  gaps: Gap[];
  overall_plan: OverallPlan | null;
};

type GapRecsResponse = {
  status: string;
  recommendations: Recommendations | null;
  error_message?: string;
};

type Props = {
  matchId: number;
  missingSkills: string[];
  planTier: string;
};

const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-green-100 text-green-700",
};

const RESOURCE_TYPE_ICONS: Record<string, string> = {
  course: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  certification: "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
  tutorial: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z",
  book: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  project: "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4",
};

export default function GapRecommendationsCard({
  matchId,
  missingSkills,
  planTier,
}: Props) {
  const [data, setData] = useState<GapRecsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const [expandedGap, setExpandedGap] = useState<number | null>(null);
  const [retrying, setRetrying] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRecs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/matches/${matchId}/gap-recs`, {
        credentials: "include",
      });
      if (!res.ok) {
        if (res.status === 429) {
          setData({
            status: "limit_reached",
            recommendations: null,
            error_message: "Daily limit reached. Upgrade for more.",
          });
          setLoading(false);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          return;
        }
        setLoading(false);
        return;
      }
      const json: GapRecsResponse = await res.json();
      setData(json);
      setLoading(false);

      if (json.status === "completed" || json.status === "failed") {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    } catch {
      setLoading(false);
    }
  }, [matchId]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleTrigger = () => {
    setTriggered(true);
    setLoading(true);
    fetchRecs();
    pollRef.current = setInterval(fetchRecs, 3000);
  };

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/gap-recs/retry`,
        { method: "POST", credentials: "include" }
      );
      if (res.ok) {
        const json = await res.json();
        setData(json);
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(fetchRecs, 3000);
      }
    } catch {
      // ignore
    } finally {
      setRetrying(false);
    }
  };

  // Don't show if no missing skills
  if (!missingSkills || missingSkills.length === 0) return null;

  // Not yet triggered — show CTA
  if (!triggered && !data) {
    return (
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Gap Closure Plan
        </h3>
        <div className="text-center py-4">
          <p className="text-sm text-gray-600 mb-3">
            You have {missingSkills.length} skill gap{missingSkills.length !== 1 ? "s" : ""} for this role.
            Get a personalized learning plan with courses, certifications, and quick wins.
          </p>
          <button
            onClick={handleTrigger}
            className="rounded-md bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
          >
            Get personalized learning plan
          </button>
        </div>
      </div>
    );
  }

  // Loading / pending
  if (loading || (data && data.status === "pending")) {
    return (
      <div className="mt-4 rounded-lg border border-emerald-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-emerald-600">
          Gap Closure Plan
        </h3>
        <div className="flex items-center justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-3 border-emerald-600 border-t-transparent" />
          <span className="ml-3 text-sm text-emerald-600">
            Creating your personalized learning plan...
          </span>
        </div>
      </div>
    );
  }

  // Limit reached
  if (data && data.status === "limit_reached") {
    return (
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Gap Closure Plan
        </h3>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-center">
          <p className="text-sm text-amber-700">{data.error_message}</p>
          <a
            href="/settings"
            className="mt-2 inline-block rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
          >
            Upgrade Plan
          </a>
        </div>
      </div>
    );
  }

  // Failed
  if (data && data.status === "failed") {
    return (
      <div className="mt-4 rounded-lg border border-red-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Gap Closure Plan
        </h3>
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-center">
          <p className="text-sm text-red-700">
            {data.error_message || "Failed to generate learning plan."}
          </p>
          <button
            onClick={handleRetry}
            disabled={retrying}
            className="mt-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {retrying ? "Retrying..." : "Retry"}
          </button>
        </div>
      </div>
    );
  }

  // Completed
  if (!data || !data.recommendations) return null;
  const recs = data.recommendations;
  const gaps = recs.gaps || [];
  const overallPlan = recs.overall_plan;

  return (
    <div className="mt-4 rounded-lg border border-emerald-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-emerald-600">
        Gap Closure Plan
      </h3>

      {/* Overall Plan Banner (starter/pro only) */}
      {overallPlan && (
        <div className="mb-4 rounded-lg border border-emerald-100 bg-emerald-50 p-4">
          <div className="flex items-start gap-3">
            <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-emerald-800">
                Overall Learning Strategy
                <span className="ml-2 text-xs font-normal text-emerald-600">
                  Est. {overallPlan.total_time_estimate}
                </span>
              </p>
              <p className="mt-1 text-sm text-emerald-700">{overallPlan.strategy}</p>
              {overallPlan.recommended_order.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {overallPlan.recommended_order.map((skill, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700"
                    >
                      <span className="font-bold">{i + 1}.</span> {skill}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Gap Cards */}
      <div className="space-y-3">
        {gaps.map((gap, i) => {
          const isExpanded = expandedGap === i;
          return (
            <div
              key={i}
              className="rounded-lg border border-gray-200 bg-gray-50 overflow-hidden"
            >
              <button
                onClick={() => setExpandedGap(isExpanded ? null : i)}
                className="w-full px-4 py-3 text-left flex items-center justify-between hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-800">
                    {gap.skill}
                  </span>
                  {gap.priority && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${PRIORITY_COLORS[gap.priority] || "bg-gray-100 text-gray-700"}`}
                    >
                      {gap.priority}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span>{gap.time_estimate}</span>
                  <span>{isExpanded ? "\u25BC" : "\u25B6"}</span>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-gray-200 px-4 py-3 space-y-3">
                  {/* Quick Win */}
                  <div className="rounded-md border border-amber-100 bg-amber-50 p-3">
                    <p className="text-xs font-semibold text-amber-700 mb-1">
                      Quick Win (This Week)
                    </p>
                    <p className="text-sm text-amber-800">{gap.quick_win}</p>
                  </div>

                  {/* Resources */}
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-2">
                      Recommended Resources
                    </p>
                    <div className="space-y-2">
                      {gap.resources.map((r, ri) => (
                        <div
                          key={ri}
                          className="flex items-start gap-3 rounded-md border border-gray-200 bg-white p-3"
                        >
                          <svg
                            className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-600"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d={RESOURCE_TYPE_ICONS[r.type] || RESOURCE_TYPE_ICONS.course}
                            />
                          </svg>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800">
                              {r.name}
                            </p>
                            <div className="flex flex-wrap items-center gap-2 mt-0.5">
                              <span className="text-xs text-gray-500">
                                {r.provider}
                              </span>
                              <span className="text-xs text-gray-400">|</span>
                              <span className="text-xs text-gray-500">
                                ~{r.estimated_hours}h
                              </span>
                              <span className="text-xs text-gray-400">|</span>
                              <span className={`text-xs ${r.cost === "free" ? "text-emerald-600 font-medium" : "text-gray-500"}`}>
                                {r.cost === "free" ? "Free" : r.cost}
                              </span>
                            </div>
                          </div>
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600">
                            {r.type}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Portfolio Project (starter/pro only) */}
                  {gap.portfolio_project && (
                    <div className="rounded-md border border-blue-100 bg-blue-50 p-3">
                      <p className="text-xs font-semibold text-blue-700 mb-1">
                        Portfolio Project Idea
                      </p>
                      <p className="text-sm text-blue-800">
                        {gap.portfolio_project}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Free tier upgrade CTA */}
      {planTier === "free" && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-center">
          <p className="text-sm text-emerald-700">
            Upgrade for priority ordering, more resources per skill, and an overall learning strategy.
          </p>
          <a
            href="/settings"
            className="mt-2 inline-block rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Upgrade Plan
          </a>
        </div>
      )}
    </div>
  );
}
