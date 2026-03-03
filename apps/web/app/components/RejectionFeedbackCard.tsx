"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type LikelyCause = {
  factor: string;
  severity: string;
  fixable: boolean;
  how_to_fix?: string;
};

type NextStep = {
  action: string;
  priority: string;
  timeframe: string;
};

type Analysis = {
  interpretation: string;
  feedback_type: string;
  strengths: string[];
  likely_causes: LikelyCause[];
  next_steps: NextStep[];
  encouragement: string;
  similar_roles_to_consider?: string[];
};

type FeedbackResponse = {
  status: string;
  analysis: Analysis | null;
  error_message?: string;
};

type Props = {
  matchId: number;
  applicationStatus: string | null;
  planTier: string;
};

const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-green-100 text-green-700",
};

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-blue-100 text-blue-700",
};

const TIMEFRAME_LABELS: Record<string, string> = {
  immediate: "Do now",
  this_week: "This week",
  this_month: "This month",
};

const FEEDBACK_TYPE_LABELS: Record<string, string> = {
  generic: "General Rejection",
  skills_gap: "Skills Gap",
  experience: "Experience Mismatch",
  culture_fit: "Culture Fit",
  competition: "Strong Competition",
  overqualified: "Overqualified",
};

export default function RejectionFeedbackCard({
  matchId,
  applicationStatus,
  planTier,
}: Props) {
  const [data, setData] = useState<FeedbackResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const [rejectionEmail, setRejectionEmail] = useState("");
  const [showEmailInput, setShowEmailInput] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchFeedback = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/rejection-feedback`,
        { credentials: "include" }
      );
      if (!res.ok) {
        setLoading(false);
        return;
      }
      const json: FeedbackResponse = await res.json();
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

  const handleTrigger = async () => {
    setTriggered(true);
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/rejection-feedback`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rejection_email: rejectionEmail.trim() || null,
          }),
        }
      );
      if (!res.ok) {
        if (res.status === 429) {
          setData({
            status: "limit_reached",
            analysis: null,
            error_message: "Daily limit reached. Upgrade for more.",
          });
          setLoading(false);
          return;
        }
        setLoading(false);
        return;
      }
      const json: FeedbackResponse = await res.json();
      setData(json);
      setLoading(false);
      pollRef.current = setInterval(fetchFeedback, 3000);
    } catch {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/rejection-feedback/retry`,
        { method: "POST", credentials: "include" }
      );
      if (res.ok) {
        const json = await res.json();
        setData(json);
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(fetchFeedback, 3000);
      }
    } catch {
      // ignore
    } finally {
      setRetrying(false);
    }
  };

  // Only show for rejected applications
  if (applicationStatus !== "rejected") return null;

  // Not yet triggered — show CTA
  if (!triggered && !data) {
    return (
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Rejection Feedback
        </h3>
        <div className="py-4">
          <p className="text-center text-sm text-gray-600 mb-3">
            Get AI-powered insights on why this rejection may have happened and
            what you can do next.
          </p>
          {planTier === "free" ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-center">
              <p className="text-sm text-amber-700">
                Rejection insights are available on Starter and Pro plans.
              </p>
              <a
                href="/settings"
                className="mt-2 inline-block rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
              >
                Upgrade Plan
              </a>
            </div>
          ) : (
            <div className="space-y-3">
              <button
                onClick={() => setShowEmailInput(!showEmailInput)}
                className="mx-auto block text-xs text-indigo-600 hover:text-indigo-700 underline"
              >
                {showEmailInput
                  ? "Skip email paste"
                  : "Have a rejection email? Paste it for deeper analysis"}
              </button>
              {showEmailInput && (
                <textarea
                  value={rejectionEmail}
                  onChange={(e) => setRejectionEmail(e.target.value)}
                  placeholder="Paste the rejection email here (optional)..."
                  className="w-full rounded-md border border-gray-300 p-3 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  rows={4}
                />
              )}
              <div className="text-center">
                <button
                  onClick={handleTrigger}
                  className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
                >
                  Get Rejection Insights
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Loading / pending
  if (loading || (data && data.status === "pending")) {
    return (
      <div className="mt-4 rounded-lg border border-indigo-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-indigo-600">
          Rejection Feedback
        </h3>
        <div className="flex items-center justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent" />
          <span className="ml-3 text-sm text-indigo-600">
            Analyzing your application...
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
          Rejection Feedback
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
          Rejection Feedback
        </h3>
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-center">
          <p className="text-sm text-red-700">
            {data.error_message || "Failed to generate feedback."}
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
  if (!data || !data.analysis) return null;
  const a = data.analysis;

  return (
    <div className="mt-4 rounded-lg border border-indigo-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-indigo-600">
        Rejection Feedback
      </h3>

      {/* Feedback type badge + interpretation */}
      <div className="mb-4 rounded-lg border border-indigo-100 bg-indigo-50 p-4">
        <div className="flex items-start gap-3">
          <svg
            className="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="rounded-full bg-indigo-200 px-2 py-0.5 text-xs font-medium text-indigo-800">
                {FEEDBACK_TYPE_LABELS[a.feedback_type] || a.feedback_type}
              </span>
            </div>
            <p className="text-sm text-indigo-800">{a.interpretation}</p>
          </div>
        </div>
      </div>

      {/* Strengths */}
      {a.strengths && a.strengths.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">
            What You Did Well
          </p>
          <div className="space-y-1">
            {a.strengths.map((s, i) => (
              <div key={i} className="flex items-start gap-2">
                <svg
                  className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <span className="text-sm text-gray-700">{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Likely Causes */}
      {a.likely_causes && a.likely_causes.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">
            Likely Causes
          </p>
          <div className="space-y-2">
            {a.likely_causes.map((c, i) => (
              <div
                key={i}
                className="rounded-md border border-gray-200 bg-gray-50 p-3"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-gray-800">
                    {c.factor}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${SEVERITY_COLORS[c.severity] || "bg-gray-100 text-gray-700"}`}
                  >
                    {c.severity}
                  </span>
                  {c.fixable && (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                      fixable
                    </span>
                  )}
                </div>
                {c.how_to_fix && (
                  <p className="text-sm text-gray-600 mt-1">{c.how_to_fix}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Next Steps */}
      {a.next_steps && a.next_steps.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">
            Recommended Next Steps
          </p>
          <div className="space-y-2">
            {a.next_steps.map((ns, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-md border border-gray-200 bg-white p-3"
              >
                <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
                  {i + 1}
                </span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">
                    {ns.action}
                  </p>
                  <div className="mt-1 flex gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${PRIORITY_COLORS[ns.priority] || "bg-gray-100 text-gray-700"}`}
                    >
                      {ns.priority}
                    </span>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                      {TIMEFRAME_LABELS[ns.timeframe] || ns.timeframe}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Similar Roles */}
      {a.similar_roles_to_consider && a.similar_roles_to_consider.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">
            Roles Worth Exploring
          </p>
          <div className="flex flex-wrap gap-2">
            {a.similar_roles_to_consider.map((role, i) => (
              <span
                key={i}
                className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-sm text-indigo-700"
              >
                {role}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Encouragement */}
      {a.encouragement && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-start gap-3">
            <svg
              className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
              />
            </svg>
            <p className="text-sm text-emerald-800">{a.encouragement}</p>
          </div>
        </div>
      )}
    </div>
  );
}
