"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type StarAnswer = {
  situation: string;
  task: string;
  action: string;
  result: string;
};

type LikelyQuestion = {
  category: string;
  question: string;
  star_answer: StarAnswer;
  source: string;
};

type CompanyInsights = {
  culture_signals: string[];
  values: string[];
  concerns: string[];
};

type GapStrategy = {
  skill: string;
  severity: string;
  strategy: string;
};

type PrepContent = {
  likely_questions?: LikelyQuestion[];
  company_insights?: CompanyInsights;
  gap_strategies?: GapStrategy[];
  closing_questions?: string[];
};

type PrepData = {
  id: number;
  match_id: number;
  status: string;
  prep_content: PrepContent | null;
  error_message: string | null;
};

type Props = {
  matchId: number;
  applicationStatus: string | null;
  planTier: string;
};

const CATEGORY_COLORS: Record<string, string> = {
  Behavioral: "bg-blue-100 text-blue-800",
  Technical: "bg-purple-100 text-purple-800",
  Situational: "bg-amber-100 text-amber-800",
  "Culture Fit": "bg-green-100 text-green-800",
};

export default function InterviewPrepPanel({
  matchId,
  applicationStatus,
  planTier,
}: Props) {
  const [prep, setPrep] = useState<PrepData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedQ, setExpandedQ] = useState<number | null>(null);
  const [retrying, setRetrying] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const shouldShow =
    !!applicationStatus && ["interviewing", "offer"].includes(applicationStatus);

  const fetchPrep = useCallback(async () => {
    if (!shouldShow || planTier === "free") return;
    try {
      const res = await fetch(`${API_BASE}/api/matches/${matchId}/interview-prep`, {
        credentials: "include",
      });
      if (res.status === 404) {
        setPrep(null);
        setLoading(false);
        return;
      }
      if (!res.ok) {
        setLoading(false);
        return;
      }
      const data: PrepData = await res.json();
      setPrep(data);
      setLoading(false);

      // Stop polling once completed or failed
      if (data.status === "completed" || data.status === "failed") {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    } catch {
      setLoading(false);
    }
  }, [matchId, shouldShow, planTier]);

  useEffect(() => {
    if (!shouldShow || planTier === "free") {
      setLoading(false);
      return;
    }
    fetchPrep();
    pollRef.current = setInterval(fetchPrep, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchPrep, shouldShow, planTier]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/interview-prep/retry`,
        { method: "POST", credentials: "include" }
      );
      if (res.ok) {
        const data = await res.json();
        setPrep(data);
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(fetchPrep, 2000);
      }
    } catch {
      // ignore
    } finally {
      setRetrying(false);
    }
  };

  // Early returns AFTER all hooks
  if (!shouldShow) return null;

  // Free tier — show upgrade CTA
  if (planTier === "free") {
    return (
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Interview Prep Coach
        </h3>
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-4 text-center">
          <p className="text-sm text-purple-700">
            Get personalized interview preparation with STAR answers, company insights,
            and closing questions.
          </p>
          <a
            href="/settings"
            className="mt-2 inline-block rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700"
          >
            Upgrade to Starter
          </a>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Interview Prep Coach
        </h3>
        <div className="flex items-center justify-center py-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="ml-3 text-sm text-gray-500">Loading...</span>
        </div>
      </div>
    );
  }

  if (!prep) return null;

  // Pending/processing state
  if (prep.status === "pending" || prep.status === "processing") {
    return (
      <div className="mt-4 rounded-lg border border-purple-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-purple-600">
          Interview Prep Coach
        </h3>
        <div className="flex items-center justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-3 border-purple-600 border-t-transparent" />
          <span className="ml-3 text-sm text-purple-600">
            Generating your personalized interview prep...
          </span>
        </div>
      </div>
    );
  }

  // Failed state
  if (prep.status === "failed") {
    return (
      <div className="mt-4 rounded-lg border border-red-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Interview Prep Coach
        </h3>
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-center">
          <p className="text-sm text-red-700">
            {prep.error_message || "Interview prep generation failed."}
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

  // Completed — render prep content
  const content = prep.prep_content;
  if (!content) return null;

  const questions = content.likely_questions || [];
  const insights = content.company_insights;
  const gapStrategies = content.gap_strategies;
  const closingQuestions = content.closing_questions || [];

  // Group questions by category
  const grouped: Record<string, LikelyQuestion[]> = {};
  for (const q of questions) {
    const cat = q.category || "General";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(q);
  }

  return (
    <div className="mt-4 rounded-lg border border-purple-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-purple-600">
        Interview Prep Coach
      </h3>

      {/* Likely Questions */}
      {questions.length > 0 && (
        <div className="mb-5">
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            <svg className="h-4 w-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Likely Interview Questions
          </h4>
          {Object.entries(grouped).map(([category, qs]) => (
            <div key={category} className="mb-3">
              <span className={`mb-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_COLORS[category] || "bg-gray-100 text-gray-700"}`}>
                {category}
              </span>
              {qs.map((q, qi) => {
                const globalIdx = questions.indexOf(q);
                const isExpanded = expandedQ === globalIdx;
                return (
                  <div key={qi} className="ml-1 border-l-2 border-purple-100 pl-3 py-1">
                    <button
                      onClick={() => setExpandedQ(isExpanded ? null : globalIdx)}
                      className="w-full text-left text-sm text-gray-800 hover:text-purple-700"
                    >
                      <span className="font-medium">{q.question}</span>
                      <span className="ml-1 text-xs text-gray-400">{isExpanded ? "▼" : "▶"}</span>
                    </button>
                    {isExpanded && (
                      <div className="mt-1 rounded-md bg-purple-50 p-3 text-sm">
                        <div className="space-y-1.5">
                          <p><span className="font-semibold text-purple-700">Situation:</span> {q.star_answer.situation}</p>
                          <p><span className="font-semibold text-purple-700">Task:</span> {q.star_answer.task}</p>
                          <p><span className="font-semibold text-purple-700">Action:</span> {q.star_answer.action}</p>
                          <p><span className="font-semibold text-purple-700">Result:</span> {q.star_answer.result}</p>
                        </div>
                        <p className="mt-2 text-xs text-gray-500 italic">Source: {q.source}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {/* Company Insights */}
      {insights && (
        <div className="mb-5">
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            <svg className="h-4 w-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            Company Insights
          </h4>
          <div className="grid gap-3 sm:grid-cols-3">
            {insights.culture_signals && insights.culture_signals.length > 0 && (
              <div className="rounded-md border border-blue-100 bg-blue-50 p-3">
                <p className="mb-1 text-xs font-semibold text-blue-700">Culture Signals</p>
                <ul className="space-y-1 text-xs text-blue-800">
                  {insights.culture_signals.map((s, i) => (
                    <li key={i}>• {s}</li>
                  ))}
                </ul>
              </div>
            )}
            {insights.values && insights.values.length > 0 && (
              <div className="rounded-md border border-green-100 bg-green-50 p-3">
                <p className="mb-1 text-xs font-semibold text-green-700">Values</p>
                <ul className="space-y-1 text-xs text-green-800">
                  {insights.values.map((v, i) => (
                    <li key={i}>• {v}</li>
                  ))}
                </ul>
              </div>
            )}
            {insights.concerns && insights.concerns.length > 0 && (
              <div className="rounded-md border border-amber-100 bg-amber-50 p-3">
                <p className="mb-1 text-xs font-semibold text-amber-700">Watch For</p>
                <ul className="space-y-1 text-xs text-amber-800">
                  {insights.concerns.map((c, i) => (
                    <li key={i}>• {c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Gap Strategies (Pro only) */}
      {gapStrategies && gapStrategies.length > 0 && (
        <div className="mb-5">
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            <svg className="h-4 w-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Gap Strategies
            <span className="rounded-full bg-purple-600 px-1.5 py-0.5 text-[10px] font-bold text-white">PRO</span>
          </h4>
          <div className="space-y-2">
            {gapStrategies.map((g, i) => (
              <div key={i} className="rounded-md border border-gray-200 bg-gray-50 p-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-800">{g.skill}</span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                    g.severity === "critical" ? "bg-red-100 text-red-700" :
                    g.severity === "moderate" ? "bg-amber-100 text-amber-700" :
                    "bg-green-100 text-green-700"
                  }`}>
                    {g.severity}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-600">{g.strategy}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Gap Strategies — Starter users see upgrade prompt */}
      {!gapStrategies && planTier === "starter" && (
        <div className="mb-5">
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            Gap Strategies
            <span className="rounded-full bg-purple-600 px-1.5 py-0.5 text-[10px] font-bold text-white">PRO</span>
          </h4>
          <div className="rounded-md border border-purple-100 bg-purple-50 p-3 text-center">
            <p className="text-xs text-purple-700">
              Upgrade to Pro to see gap strategies for addressing missing skills in your interview.
            </p>
          </div>
        </div>
      )}

      {/* Closing Questions */}
      {closingQuestions.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            <svg className="h-4 w-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
            Questions to Ask
          </h4>
          <ol className="ml-5 list-decimal space-y-1 text-sm text-gray-700">
            {closingQuestions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
