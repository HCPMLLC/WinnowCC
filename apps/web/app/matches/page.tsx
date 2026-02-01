"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";

type Job = {
  id: number;
  company: string;
  url: string;
  title: string;
  description_text: string;
  location: string;
  application_deadline: string | null;
  hiring_manager_name: string | null;
  hiring_manager_email: string | null;
  hiring_manager_phone: string | null;
};

type MatchReasons = {
  matched_skills?: string[];
  missing_skills?: string[];
  title_alignment?: number;
  location_fit?: number;
  salary_fit?: number;
  experience_bonus?: number;
  [key: string]: unknown;
};

type Match = {
  id: number;
  job: Job;
  match_score: number;
  interview_readiness_score: number;
  offer_probability: number;
  reasons: MatchReasons;
};

type TailorStatus = {
  status: string;
  resume_url?: string | null;
  cover_letter_url?: string | null;
  error_message?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function MatchesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [showReasons, setShowReasons] = useState<Record<number, boolean>>({});
  const [statusByJob, setStatusByJob] = useState<Record<number, string>>({});
  const [draftStatusByMatch, setDraftStatusByMatch] = useState<Record<number, string>>({});
  const [linksByJob, setLinksByJob] = useState<
    Record<number, { resume?: string; cover?: string }>
  >({});
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);

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

  useEffect(() => {
    const loadMatches = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/matches`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load matches.");
        }
        const payload = (await response.json()) as Match[];
        setMatches(payload);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load matches.";
        setError(message);
      }
    };
    void loadMatches();
  }, []);

  const toggleExpand = (matchId: number) => {
    setExpanded((current) => ({ ...current, [matchId]: !current[matchId] }));
  };

  const toggleReasons = (matchId: number) => {
    setShowReasons((current) => ({ ...current, [matchId]: !current[matchId] }));
  };

  const handlePrepare = async (jobId: number) => {
    setStatusByJob((current) => ({ ...current, [jobId]: "Queued..." }));
    setLinksByJob((current) => ({ ...current, [jobId]: {} }));

    try {
      const response = await fetch(`${API_BASE}/api/tailor/${jobId}`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to start tailoring.");
      }
      const payload = (await response.json()) as { job_id: string };

      const maxTries = 20;
      for (let i = 0; i < maxTries; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const statusResponse = await fetch(
          `${API_BASE}/api/tailor/status/${payload.job_id}`,
          { credentials: "include" }
        );
        if (!statusResponse.ok) {
          throw new Error("Failed to fetch tailoring status.");
        }
        const statusPayload = (await statusResponse.json()) as TailorStatus;
        if (statusPayload.status === "finished") {
          setStatusByJob((current) => ({
            ...current,
            [jobId]: "Ready",
          }));
          setLinksByJob((current) => ({
            ...current,
            [jobId]: {
              resume: statusPayload.resume_url ?? undefined,
              cover: statusPayload.cover_letter_url ?? undefined,
            },
          }));
          return;
        }
        if (statusPayload.status === "failed") {
          throw new Error(statusPayload.error_message || "Tailoring failed.");
        }
        setStatusByJob((current) => ({
          ...current,
          [jobId]: `Working... (${i + 1}/${maxTries})`,
        }));
      }
      setStatusByJob((current) => ({
        ...current,
        [jobId]: "Still processing. Check back soon.",
      }));
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Tailoring failed.";
      setStatusByJob((current) => ({ ...current, [jobId]: message }));
    }
  };

  const handleCreateDraft = async (match: Match) => {
    setDraftStatusByMatch((current) => ({ ...current, [match.id]: "Creating..." }));

    try {
      const response = await fetch(`${API_BASE}/api/mjass/drafts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          match_id: match.id,
          job_url: match.job.url,
          job_title: match.job.title,
          company: match.job.company,
          location: match.job.location,
          source: "resumematch",
          application_mode: "review_required",
          draft_payload: {
            job_id: match.job.id,
            match_score: match.match_score,
            interview_readiness: match.interview_readiness_score,
            offer_probability: match.offer_probability,
          },
          explain: {
            match_score: match.match_score,
            interview_readiness_score: match.interview_readiness_score,
            offer_probability: match.offer_probability,
            ...match.reasons,
          },
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to create draft");
      }

      const result = (await response.json()) as { id: number };
      setDraftStatusByMatch((current) => ({
        ...current,
        [match.id]: `Draft #${result.id} created`,
      }));
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to create draft";
      setDraftStatusByMatch((current) => ({ ...current, [match.id]: message }));
    }
  };

  const handleRefresh = async () => {
    setRefreshStatus("Refreshing matches...");
    try {
      const response = await fetch(`${API_BASE}/api/matches/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to refresh matches.");
      }
      setRefreshStatus("Refresh queued. Reload in a moment.");
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to refresh matches.";
      setRefreshStatus(message);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Top Matches</h1>
        <p className="text-sm text-slate-600">
          Jobs matched to your profile with AI-powered scoring and explainability.
        </p>
        <div className="mt-2 flex items-center gap-4">
          <button
            type="button"
            onClick={handleRefresh}
            className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
          >
            Refresh matches
          </button>
          <button
            type="button"
            onClick={() => router.push("/mjass/review")}
            className="rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700"
          >
            View Drafts
          </button>
          {refreshStatus ? (
            <span className="text-xs text-slate-500">{refreshStatus}</span>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="flex flex-col gap-4">
        {matches.map((match) => {
          const job = match.job;
          const shortDescription = job.description_text.slice(0, 200);
          const isExpanded = expanded[match.id];
          const reasonsVisible = showReasons[match.id];
          const statusText = statusByJob[job.id];
          const draftStatus = draftStatusByMatch[match.id];
          const links = linksByJob[job.id] || {};
          const reasons = match.reasons || {};

          return (
            <div
              key={match.id}
              className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              {/* Header */}
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    {job.title}
                  </h2>
                  <p className="text-sm text-slate-600">
                    {job.company} - {job.location}
                  </p>
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 text-xs text-blue-600 underline"
                  >
                    View job posting
                  </a>
                </div>

                {/* Scores */}
                <div className="flex gap-3">
                  <div className="rounded-xl bg-emerald-50 px-3 py-2 text-center">
                    <div className="text-xl font-bold text-emerald-700">
                      {match.match_score}
                    </div>
                    <div className="text-xs text-emerald-600">Match</div>
                  </div>
                  <div className="rounded-xl bg-blue-50 px-3 py-2 text-center">
                    <div className="text-xl font-bold text-blue-700">
                      {match.interview_readiness_score}
                    </div>
                    <div className="text-xs text-blue-600">Interview</div>
                  </div>
                  <div className="rounded-xl bg-purple-50 px-3 py-2 text-center">
                    <div className="text-xl font-bold text-purple-700">
                      {match.offer_probability}
                    </div>
                    <div className="text-xs text-purple-600">Offer %</div>
                  </div>
                </div>
              </div>

              {/* Why You Matched */}
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => toggleReasons(match.id)}
                  className="text-sm font-medium text-slate-700 underline"
                >
                  {reasonsVisible ? "Hide" : "Show"} why you matched
                </button>

                {reasonsVisible && (
                  <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      {reasons.matched_skills && reasons.matched_skills.length > 0 && (
                        <div>
                          <div className="text-xs font-semibold uppercase text-emerald-700">
                            Matched Skills
                          </div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {reasons.matched_skills.map((skill, i) => (
                              <span
                                key={i}
                                className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {reasons.missing_skills && reasons.missing_skills.length > 0 && (
                        <div>
                          <div className="text-xs font-semibold uppercase text-amber-700">
                            Skills to Highlight
                          </div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {reasons.missing_skills.map((skill, i) => (
                              <span
                                key={i}
                                className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="md:col-span-2">
                        <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                          {reasons.title_alignment !== undefined && (
                            <div className="rounded-lg bg-white p-2">
                              <span className="text-slate-500">Title Fit:</span>{" "}
                              <span className="font-semibold">{reasons.title_alignment}</span>
                            </div>
                          )}
                          {reasons.location_fit !== undefined && (
                            <div className="rounded-lg bg-white p-2">
                              <span className="text-slate-500">Location:</span>{" "}
                              <span className="font-semibold">{reasons.location_fit}</span>
                            </div>
                          )}
                          {reasons.salary_fit !== undefined && (
                            <div className="rounded-lg bg-white p-2">
                              <span className="text-slate-500">Salary:</span>{" "}
                              <span className="font-semibold">{reasons.salary_fit}</span>
                            </div>
                          )}
                          {reasons.experience_bonus !== undefined && (
                            <div className="rounded-lg bg-white p-2">
                              <span className="text-slate-500">Experience:</span>{" "}
                              <span className="font-semibold">+{reasons.experience_bonus}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Description */}
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => toggleExpand(match.id)}
                  className="text-xs text-slate-600 underline"
                >
                  {isExpanded ? "Hide description" : "Show description"}
                </button>
                <p className="mt-2 text-sm text-slate-600">
                  {isExpanded ? job.description_text : `${shortDescription}...`}
                </p>
              </div>

              {/* Actions */}
              <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  onClick={() => handlePrepare(job.id)}
                  className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
                >
                  Prepare Materials
                </button>
                <button
                  type="button"
                  onClick={() => handleCreateDraft(match)}
                  className="rounded-full bg-blue-600 px-4 py-2 text-xs font-semibold text-white"
                >
                  Create Application Draft
                </button>

                {statusText && (
                  <span className="text-xs text-slate-600">{statusText}</span>
                )}
                {draftStatus && (
                  <span className="text-xs text-blue-600">{draftStatus}</span>
                )}

                {(links.resume || links.cover) && (
                  <div className="flex gap-2 text-xs">
                    {links.resume && (
                      <a className="text-slate-700 underline" href={`${API_BASE}${links.resume}`} target="_blank" rel="noreferrer">
                        Resume
                      </a>
                    )}
                    {links.cover && (
                      <a className="text-slate-700 underline" href={`${API_BASE}${links.cover}`} target="_blank" rel="noreferrer">
                        Cover Letter
                      </a>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {matches.length === 0 && (
          <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
            No matches yet. Click "Refresh matches" to find jobs that match your profile.
          </div>
        )}
      </div>
    </main>
  );
}
