"use client";

import { useState, useEffect } from "react";

interface Prediction {
  predicted_stage:
    | "submitted"
    | "screening"
    | "review"
    | "decision"
    | "stale";
  confidence: "low" | "medium" | "high";
  days_since_applied: number;
  days_job_open: number;
  explanation: string;
  next_milestone: string;
  tips: string[];
  match_score: number;
}

const stageConfig: Record<
  string,
  { label: string; color: string; icon: string }
> = {
  submitted: { label: "Submitted", color: "bg-blue-500", icon: "\u{1F4E4}" },
  screening: { label: "Screening", color: "bg-yellow-500", icon: "\u{1F440}" },
  review: { label: "In Review", color: "bg-purple-500", icon: "\u{1F4CB}" },
  decision: { label: "Decision", color: "bg-green-500", icon: "\u2696\uFE0F" },
  stale: { label: "May Be Stale", color: "bg-gray-400", icon: "\u23F0" },
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function StatusPrediction({ matchId }: { matchId: number }) {
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetch(`${API_BASE}/api/matches/${matchId}/status-prediction`, {
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
          setPrediction(data as Prediction);
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) {
    return (
      <div className="mt-4 h-24 animate-pulse rounded-lg bg-gray-100" />
    );
  }
  if (error || !prediction) return null;

  const stage = stageConfig[prediction.predicted_stage] ?? stageConfig.submitted;

  const stageOrder = ["submitted", "screening", "review", "decision"];
  const currentIndex = stageOrder.indexOf(prediction.predicted_stage);
  const progress =
    prediction.predicted_stage === "stale"
      ? 100
      : ((currentIndex + 1) / stageOrder.length) * 100;

  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Application Status Estimate
        </h3>
        <span
          className={`rounded-full px-2 py-1 text-xs ${
            prediction.confidence === "high"
              ? "bg-green-100 text-green-800"
              : prediction.confidence === "medium"
                ? "bg-yellow-100 text-yellow-800"
                : "bg-gray-100 text-gray-600"
          }`}
        >
          {prediction.confidence} confidence
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="mb-1 flex justify-between text-xs text-gray-500">
          {stageOrder.map((s, i) => (
            <span
              key={s}
              className={
                i <= currentIndex ? "font-medium text-emerald-600" : ""
              }
            >
              {stageConfig[s].icon}
            </span>
          ))}
        </div>
        <div className="h-2 rounded-full bg-gray-200">
          <div
            className={`h-2 rounded-full transition-all ${stage.color}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Current stage */}
      <div className="mb-3 flex items-center gap-2">
        <span className="text-2xl">{stage.icon}</span>
        <div>
          <p className="font-medium text-gray-900">{stage.label}</p>
          <p className="text-sm text-gray-500">
            Day {prediction.days_since_applied} of your application
          </p>
        </div>
      </div>

      {/* Explanation */}
      <p className="mb-3 text-sm text-gray-600">{prediction.explanation}</p>

      {/* Next milestone */}
      <div className="rounded bg-blue-50 p-2 text-sm text-blue-800">
        <strong>Next:</strong> {prediction.next_milestone}
      </div>

      {/* Tips */}
      {prediction.tips.length > 0 && (
        <p className="mt-3 text-xs text-gray-500">
          {prediction.tips[0]}
        </p>
      )}
    </div>
  );
}
