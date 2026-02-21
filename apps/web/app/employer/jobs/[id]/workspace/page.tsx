"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface FeedbackEntry {
  id: number;
  candidate_profile_id: number;
  interviewer_user_id: number | null;
  interview_type: string;
  rating: number | null;
  recommendation: string | null;
  strengths: string | null;
  concerns: string | null;
  notes: string | null;
  submitted_at: string | null;
}

interface Workspace {
  job_id: number;
  title: string;
  status: string;
  feedback: FeedbackEntry[];
}

interface Scorecard {
  candidate_profile_id: number;
  total_reviews: number;
  avg_rating: number | null;
  reviews: {
    interviewer_id: number | null;
    type: string;
    rating: number | null;
    recommendation: string | null;
  }[];
}

const RECOMMENDATION_COLORS: Record<string, string> = {
  strong_yes: "bg-green-100 text-green-800",
  yes: "bg-emerald-100 text-emerald-800",
  neutral: "bg-slate-100 text-slate-700",
  no: "bg-amber-100 text-amber-800",
  strong_no: "bg-red-100 text-red-800",
};

export default function WorkspacePage() {
  const params = useParams();
  const jobId = params.id as string;

  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [scorecards, setScorecards] = useState<Scorecard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Feedback form state
  const [candidateId, setCandidateId] = useState("");
  const [interviewType, setInterviewType] = useState("phone_screen");
  const [rating, setRating] = useState("3");
  const [recommendation, setRecommendation] = useState("neutral");
  const [strengths, setStrengths] = useState("");
  const [concerns, setConcerns] = useState("");

  useEffect(() => {
    fetchData();
  }, [jobId]);

  async function fetchData() {
    try {
      const [wsRes, scRes] = await Promise.all([
        fetch(`${API_BASE}/api/employer/jobs/${jobId}/workspace`, {
          credentials: "include",
        }),
        fetch(`${API_BASE}/api/employer/jobs/${jobId}/scorecard`, {
          credentials: "include",
        }),
      ]);

      if (wsRes.ok) setWorkspace(await wsRes.json());
      else throw new Error("Failed to load workspace");

      if (scRes.ok) {
        const data = await scRes.json();
        setScorecards(data.scorecards || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitFeedback(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${jobId}/feedback`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_profile_id: Number(candidateId),
            interview_type: interviewType,
            rating: Number(rating),
            recommendation,
            strengths: strengths || null,
            concerns: concerns || null,
          }),
        },
      );
      if (res.ok) {
        setShowForm(false);
        setCandidateId("");
        setStrengths("");
        setConcerns("");
        fetchData();
      }
    } catch {
      // Ignore
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
        <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            Hiring Workspace
          </h1>
          <p className="mt-1 text-slate-600">
            {workspace?.title} &middot;{" "}
            <span className="capitalize">{workspace?.status}</span>
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          {showForm ? "Cancel" : "Add Feedback"}
        </button>
      </div>

      {/* Feedback Form */}
      {showForm && (
        <form
          onSubmit={submitFeedback}
          className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Submit Interview Feedback
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Candidate Profile ID
              </label>
              <input
                type="number"
                value={candidateId}
                onChange={(e) => setCandidateId(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Interview Type
              </label>
              <select
                value={interviewType}
                onChange={(e) => setInterviewType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="phone_screen">Phone Screen</option>
                <option value="technical">Technical</option>
                <option value="behavioral">Behavioral</option>
                <option value="panel">Panel</option>
                <option value="final">Final</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Rating (1-5)
              </label>
              <select
                value={rating}
                onChange={(e) => setRating(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Recommendation
              </label>
              <select
                value={recommendation}
                onChange={(e) => setRecommendation(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="strong_yes">Strong Yes</option>
                <option value="yes">Yes</option>
                <option value="neutral">Neutral</option>
                <option value="no">No</option>
                <option value="strong_no">Strong No</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700">
                Strengths
              </label>
              <textarea
                value={strengths}
                onChange={(e) => setStrengths(e.target.value)}
                rows={2}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700">
                Concerns
              </label>
              <textarea
                value={concerns}
                onChange={(e) => setConcerns(e.target.value)}
                rows={2}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
          <button
            type="submit"
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Submit Feedback
          </button>
        </form>
      )}

      {/* Scorecards */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Candidate Scorecards
        </h2>
        {scorecards.length === 0 ? (
          <p className="text-sm text-slate-500">
            No feedback submitted yet.
          </p>
        ) : (
          <div className="space-y-4">
            {scorecards.map((sc) => (
              <div
                key={sc.candidate_profile_id}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-slate-900">
                    Candidate #{sc.candidate_profile_id}
                  </h3>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-500">
                      {sc.total_reviews} review(s)
                    </span>
                    {sc.avg_rating != null && (
                      <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-sm font-medium text-blue-800">
                        Avg: {sc.avg_rating}/5
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
                  {sc.reviews.map((r, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-slate-100 p-3"
                    >
                      <p className="text-xs text-slate-500 capitalize">
                        {r.type.replace("_", " ")}
                      </p>
                      <div className="mt-1 flex items-center gap-2">
                        {r.rating != null && (
                          <span className="text-sm font-medium text-slate-900">
                            {r.rating}/5
                          </span>
                        )}
                        {r.recommendation && (
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                              RECOMMENDATION_COLORS[r.recommendation] ||
                              "bg-slate-100"
                            }`}
                          >
                            {r.recommendation.replace("_", " ")}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Feedback */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Activity Feed
        </h2>
        {(workspace?.feedback ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No activity yet.</p>
        ) : (
          <div className="space-y-2">
            {workspace?.feedback.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3"
              >
                <div>
                  <span className="text-sm font-medium text-slate-900">
                    Candidate #{f.candidate_profile_id}
                  </span>
                  <span className="ml-2 text-xs text-slate-500 capitalize">
                    {f.interview_type.replace("_", " ")}
                  </span>
                  {f.recommendation && (
                    <span
                      className={`ml-2 rounded-full px-2 py-0.5 text-xs font-medium ${
                        RECOMMENDATION_COLORS[f.recommendation] ||
                        "bg-slate-100"
                      }`}
                    >
                      {f.recommendation.replace("_", " ")}
                    </span>
                  )}
                </div>
                <span className="text-xs text-slate-400">
                  {f.submitted_at
                    ? new Date(f.submitted_at).toLocaleString()
                    : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
