"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Suggestion = {
  category: string;
  section_ref: string;
  priority: "high" | "medium" | "low";
  current_issue: string;
  suggestion: string;
  example: string;
  impact: string;
};

type OverallAssessment = {
  strengths: string[];
  biggest_opportunity: string;
  estimated_improvement: string;
};

export type EnhancementData = {
  status: "not_generated" | "generating" | "completed" | "failed";
  suggestions?: Suggestion[];
  overall_assessment?: OverallAssessment | null;
  generated_at?: string | null;
};

const PRIORITY_STYLES: Record<string, { dot: string; badge: string; label: string }> = {
  high: {
    dot: "bg-red-500",
    badge: "bg-red-100 text-red-700",
    label: "High",
  },
  medium: {
    dot: "bg-amber-500",
    badge: "bg-amber-100 text-amber-700",
    label: "Medium",
  },
  low: {
    dot: "bg-blue-500",
    badge: "bg-blue-100 text-blue-700",
    label: "Low",
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  experience: "Experience",
  skills: "Skills",
  education: "Education",
  summary: "Summary",
  preferences: "Preferences",
  formatting: "Formatting",
};

export default function EnhancementSuggestions({
  data,
  onRegenerate,
}: {
  data: EnhancementData;
  onRegenerate: () => void;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (data.status === "not_generated") return null;

  if (data.status === "generating") {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Improve Your Profile</h2>
        <div className="mt-4 flex items-center gap-3 text-sm text-slate-500">
          <svg
            className="h-5 w-5 animate-spin text-slate-400"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
          Analyzing your profile for improvement suggestions...
        </div>
      </section>
    );
  }

  if (data.status === "failed") {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Improve Your Profile</h2>
        <p className="mt-2 text-sm text-slate-500">
          We couldn&apos;t generate suggestions this time.
        </p>
        <button
          type="button"
          onClick={onRegenerate}
          className="mt-3 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Retry
        </button>
      </section>
    );
  }

  // completed
  const suggestions = data.suggestions || [];
  const assessment = data.overall_assessment;

  if (suggestions.length === 0 && !assessment) return null;

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Improve Your Profile</h2>
        <button
          type="button"
          onClick={onRegenerate}
          className="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {assessment && (
        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
          {assessment.strengths && assessment.strengths.length > 0 && (
            <div className="mb-2">
              <span className="text-sm font-medium text-emerald-800">
                Strengths:{" "}
              </span>
              <span className="text-sm text-emerald-700">
                {assessment.strengths.join(", ")}
              </span>
            </div>
          )}
          {assessment.biggest_opportunity && (
            <div>
              <span className="text-sm font-medium text-emerald-800">
                Biggest opportunity:{" "}
              </span>
              <span className="text-sm text-emerald-700">
                {assessment.biggest_opportunity}
              </span>
            </div>
          )}
          {assessment.estimated_improvement && (
            <div className="mt-1 text-xs text-emerald-600">
              Estimated match improvement: {assessment.estimated_improvement}
            </div>
          )}
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="mt-4 flex flex-col gap-3">
          {suggestions.map((s, i) => {
            const style = PRIORITY_STYLES[s.priority] || PRIORITY_STYLES.low;
            const isExpanded = expandedIdx === i;
            return (
              <div
                key={i}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
              >
                <button
                  type="button"
                  onClick={() => setExpandedIdx(isExpanded ? null : i)}
                  className="flex w-full items-start gap-3 text-left"
                >
                  <span
                    className={`mt-1.5 inline-block h-2 w-2 flex-shrink-0 rounded-full ${style.dot}`}
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${style.badge}`}
                      >
                        {style.label}
                      </span>
                      <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                        {CATEGORY_LABELS[s.category] || s.category}
                      </span>
                    </div>
                    <p className="mt-1 text-sm font-medium text-slate-800">
                      {s.suggestion}
                    </p>
                  </div>
                  <svg
                    className={`mt-1 h-4 w-4 flex-shrink-0 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>

                {isExpanded && (
                  <div className="mt-3 ml-5 flex flex-col gap-2 border-t border-slate-200 pt-3">
                    {s.section_ref && (
                      <div className="text-xs text-slate-500">
                        Section: {s.section_ref}
                      </div>
                    )}
                    {s.current_issue && (
                      <div>
                        <span className="text-xs font-medium text-slate-600">
                          Issue:{" "}
                        </span>
                        <span className="text-xs text-slate-500">
                          {s.current_issue}
                        </span>
                      </div>
                    )}
                    {s.example && (
                      <div className="rounded-xl bg-white p-3 text-xs text-slate-600">
                        {s.example}
                      </div>
                    )}
                    {s.impact && (
                      <div className="text-xs text-slate-500">
                        Impact: {s.impact}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
