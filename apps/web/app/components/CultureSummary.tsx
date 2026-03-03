"use client";

import { useState, useEffect } from "react";

interface CultureData {
  summary: string;
  values: string[];
  work_style: string;
  pace: string;
  remote_culture: string;
  growth_focus: string;
  signals: {
    positive: string[];
    watch_for: string[];
  };
  error?: string;
}

const workStyleLabels: Record<string, string> = {
  collaborative: "Collaborative",
  independent: "Independent",
  hybrid: "Hybrid",
  structured: "Structured",
  flexible: "Flexible",
};

const paceLabels: Record<string, string> = {
  "fast-paced": "Fast-Paced",
  steady: "Steady",
  relaxed: "Relaxed",
  intense: "Intense",
  balanced: "Balanced",
};

const remoteLabels: Record<string, string> = {
  fully_remote: "Fully Remote",
  remote_friendly: "Remote-Friendly",
  hybrid: "Hybrid",
  in_office: "In-Office",
  unclear: "Not Specified",
};

const growthLabels: Record<string, string> = {
  high: "High Growth Focus",
  moderate: "Moderate Growth",
  low: "Low Growth Focus",
  unclear: "Not Specified",
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function CultureSummary({ jobId }: { jobId: number }) {
  const [culture, setCulture] = useState<CultureData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    setCulture(null);
    fetch(`${API_BASE}/api/jobs/${jobId}/culture`, {
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) {
          setError(true);
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data && !data.error) {
          setCulture(data as CultureData);
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <div className="mt-4 h-24 animate-pulse rounded-lg bg-gray-100" />
    );
  }
  if (error || !culture) return null;

  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Company Culture
        </h3>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs font-medium text-emerald-600 hover:text-emerald-700"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      </div>

      {/* Summary */}
      <p className="mb-3 text-sm text-gray-700">{culture.summary}</p>

      {/* Tags row */}
      <div className="mb-3 flex flex-wrap gap-2">
        {culture.work_style && culture.work_style !== "unclear" && (
          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
            {workStyleLabels[culture.work_style] ?? culture.work_style}
          </span>
        )}
        {culture.pace && culture.pace !== "unclear" && (
          <span className="rounded-full bg-purple-50 px-2.5 py-1 text-xs font-medium text-purple-700">
            {paceLabels[culture.pace] ?? culture.pace}
          </span>
        )}
        {culture.remote_culture && culture.remote_culture !== "unclear" && (
          <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700">
            {remoteLabels[culture.remote_culture] ?? culture.remote_culture}
          </span>
        )}
        {culture.growth_focus &&
          culture.growth_focus !== "unclear" && (
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
              {growthLabels[culture.growth_focus] ?? culture.growth_focus}
            </span>
          )}
      </div>

      {/* Expandable detail section */}
      {expanded && (
        <div className="space-y-3 border-t border-gray-100 pt-3">
          {/* Values */}
          {culture.values && culture.values.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase text-gray-400">
                Inferred Values
              </p>
              <div className="flex flex-wrap gap-1.5">
                {culture.values.map((v) => (
                  <span
                    key={v}
                    className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                  >
                    {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Positive signals */}
          {culture.signals?.positive && culture.signals.positive.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase text-gray-400">
                Positive Signals
              </p>
              <ul className="space-y-1">
                {culture.signals.positive.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-sm text-gray-600"
                  >
                    <span className="mt-0.5 text-green-500">+</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Watch-for signals */}
          {culture.signals?.watch_for &&
            culture.signals.watch_for.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase text-gray-400">
                  Worth Asking About
                </p>
                <ul className="space-y-1">
                  {culture.signals.watch_for.map((s, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-1.5 text-sm text-gray-500"
                    >
                      <span className="mt-0.5 text-amber-500">?</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
        </div>
      )}
    </div>
  );
}
