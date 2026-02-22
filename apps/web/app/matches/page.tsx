"use client";

import { Suspense, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";
import { useProgress } from "../hooks/useProgress";
import CandidateLayout from "../components/CandidateLayout";
import ReferralToggle from "../components/ReferralToggle";
import ApplicationStatusSelect from "../components/ApplicationStatusSelect";
import CollapsibleTip from "../components/CollapsibleTip";

type Job = {
  id: number;
  company: string;
  company_logo?: string;
  url: string;
  title: string;
  description_text: string;
  description_html?: string;
  location: string;
  job_type?: string;
  salary?: string;
  salary_min?: number;
  salary_max?: number;
  posted_date?: string;
  application_deadline: string | null;
  required_skills?: string[];
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
  resume_score?: number | null;
  cover_letter_score?: number | null;
  application_logistics_score?: number | null;
  referred?: boolean;
  interview_probability?: number | null;
  application_status?: string | null;
};

type TailorStatus = {
  status: string;
  resume_url?: string | null;
  cover_letter_url?: string | null;
  error_message?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Detect if text contains HTML tags
function containsHtml(text: string): boolean {
  const htmlTagPattern = /<\/?[a-z][\s\S]*>/i;
  return htmlTagPattern.test(text);
}

// Component to render job description with proper formatting
function JobDescription({ text, html }: { text: string; html?: string }) {
  // Use explicit HTML field if provided
  if (html) {
    return (
      <div
        className="prose prose-sm max-w-none text-gray-700 prose-headings:text-gray-900 prose-a:text-green-600 prose-strong:text-gray-900 prose-ul:list-disc prose-ol:list-decimal"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  // Check if description_text contains HTML (many sources return HTML here)
  if (containsHtml(text)) {
    return (
      <div
        className="prose prose-sm max-w-none text-gray-700 prose-headings:text-gray-900 prose-a:text-green-600 prose-strong:text-gray-900 prose-ul:list-disc prose-ol:list-decimal"
        dangerouslySetInnerHTML={{ __html: text }}
      />
    );
  }

  // Plain text - preserve whitespace
  return (
    <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
      {text}
    </div>
  );
}

const SCORE_THRESHOLD = 45;
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function MatchCard({
  match,
  isSelected,
  onSelect,
  formatSalary,
  getTimeAgo,
}: {
  match: Match;
  isSelected: boolean;
  onSelect: (id: number) => void;
  formatSalary: (job: Job) => string | null;
  getTimeAgo: (dateStr: string) => string;
}) {
  const job = match.job;
  const reasons = match.reasons || {};
  const salary = formatSalary(job);
  const timeAgo = job.posted_date ? getTimeAgo(job.posted_date) : null;

  return (
    <div
      onClick={() => onSelect(match.id)}
      className={`cursor-pointer border-b border-gray-100 px-4 py-3 transition-colors ${
        isSelected
          ? "border-l-4 border-l-green-600 bg-green-50"
          : "border-l-4 border-l-transparent hover:bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className={`text-sm font-semibold leading-tight ${isSelected ? "text-green-900" : "text-gray-900"}`}>
          {job.title}
        </h3>
        <div className="flex shrink-0 items-center gap-1">
          {match.referred && (
            <span className="rounded bg-amber-500 px-1 py-0.5 text-xs font-bold text-white">8x</span>
          )}
          <span className="rounded bg-green-600 px-1.5 py-0.5 text-xs font-bold text-white">
            {match.interview_probability ?? match.match_score}%
          </span>
        </div>
      </div>
      <div className="mt-1 flex items-center gap-2">
        {job.company_logo ? <img src={job.company_logo} alt="" className="h-4 w-4 rounded object-contain" /> : null}
        <span className="text-sm text-gray-700">{job.company}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
        <span>{job.location}</span>
        {salary && (<><span className="text-gray-300">|</span><span className="font-medium text-gray-700">{salary}</span></>)}
        {timeAgo && (<><span className="text-gray-300">|</span><span>{timeAgo}</span></>)}
      </div>
      {match.application_status && (
        <div className="mt-1.5">
          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
            match.application_status === "applied" ? "bg-yellow-100 text-yellow-800" :
            match.application_status === "interviewing" ? "bg-purple-100 text-purple-800" :
            match.application_status === "offer" ? "bg-green-100 text-green-800" :
            match.application_status === "rejected" ? "bg-red-100 text-red-800" :
            match.application_status === "saved" ? "bg-blue-100 text-blue-800" :
            "bg-gray-100 text-gray-600"
          }`}>
            {match.application_status.charAt(0).toUpperCase() + match.application_status.slice(1)}
          </span>
        </div>
      )}
      {reasons.matched_skills && reasons.matched_skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {reasons.matched_skills.slice(0, 3).map((skill, i) => (
            <span key={i} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{skill}</span>
          ))}
          {reasons.matched_skills.length > 3 && (
            <span className="text-xs text-gray-400">+{reasons.matched_skills.length - 3}</span>
          )}
        </div>
      )}
    </div>
  );
}

function MatchesPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const [statusByJob, setStatusByJob] = useState<Record<number, string>>({});
  const [draftStatusByMatch, setDraftStatusByMatch] = useState<Record<number, string>>({});
  const [linksByJob, setLinksByJob] = useState<
    Record<number, { resume?: string; cover?: string }>
  >({});
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [olderExpanded, setOlderExpanded] = useState(false);
  const refreshProg = useProgress();
  const prepareProg = useProgress();
  const [preparingJobId, setPreparingJobId] = useState<number | null>(null);
  const draftProg = useProgress();
  const [creatingDraftId, setCreatingDraftId] = useState<number | null>(null);

  const qualified = matches.filter((m) => m.match_score >= SCORE_THRESHOLD);
  const now = Date.now();
  const recentMatches = qualified.filter(
    (m) => m.job.posted_date && now - new Date(m.job.posted_date).getTime() <= SEVEN_DAYS_MS
  );
  const olderMatches = qualified.filter(
    (m) => !m.job.posted_date || now - new Date(m.job.posted_date).getTime() > SEVEN_DAYS_MS
  );

  const selectedMatch = matches.find((m) => m.id === selectedMatchId) || null;

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
        const response = await fetch(`${API_BASE}/api/matches/all`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load matches.");
        }
        const payload = (await response.json()) as Match[];
        setMatches(payload);
        const aboveThreshold = payload.filter((m) => m.match_score >= SCORE_THRESHOLD);
        if (aboveThreshold.length > 0 && !selectedMatchId) {
          setSelectedMatchId(aboveThreshold[0].id);
        }
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load matches.";
        setError(message);
      }
    };
    void loadMatches();
  }, []);

  const handlePrepare = async (jobId: number) => {
    setPreparingJobId(jobId);
    prepareProg.start();
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
    } finally {
      prepareProg.complete();
      setTimeout(() => setPreparingJobId(null), 400);
    }
  };

  const handleCreateDraft = async (match: Match) => {
    setCreatingDraftId(match.id);
    draftProg.start();
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
    } finally {
      draftProg.complete();
      setTimeout(() => setCreatingDraftId(null), 400);
    }
  };

  const handleRefresh = async () => {
    refreshProg.start();
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
    } finally {
      refreshProg.complete();
    }
  };

  const formatSalary = (job: Job) => {
    if (job.salary) return job.salary;
    if (job.salary_min && job.salary_max) {
      return `$${job.salary_min.toLocaleString()} - $${job.salary_max.toLocaleString()}`;
    }
    if (job.salary_min) return `From $${job.salary_min.toLocaleString()}`;
    if (job.salary_max) return `Up to $${job.salary_max.toLocaleString()}`;
    return null;
  };

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

  return (
    <CandidateLayout>
    <div className="flex h-[calc(100vh-8rem)] flex-col overflow-hidden rounded-lg bg-gray-100">
      {/* Header - ZipRecruiter style */}
      <header className="z-10 shrink-0 border-b border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold text-gray-900">Job Matches</h1>
            <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-sm font-medium text-green-800">
              {qualified.length} jobs
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshProg.isActive}
              className="relative overflow-hidden rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-green-700 disabled:cursor-not-allowed"
            >
              {refreshProg.isActive && (
                <span
                  className="absolute inset-y-0 left-0 bg-green-500 transition-all duration-200"
                  style={{ width: `${refreshProg.progress}%` }}
                />
              )}
              <span className="relative">
                {refreshProg.isActive ? `Refreshing... ${refreshProg.pct}%` : "Refresh"}
              </span>
            </button>
            <button
              type="button"
              onClick={() => router.push("/mjass/review")}
              className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
            >
              View Drafts
            </button>
            {refreshStatus && (
              <span className="text-sm text-gray-500">{refreshStatus}</span>
            )}
          </div>
        </div>
      </header>

      {error && (
        <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Two-column layout - ZipRecruiter style */}
      <div className="flex min-h-0 flex-1">
        {/* Left column - Job list */}
        <div className="w-[340px] shrink-0 overflow-y-auto border-r border-gray-200 bg-white">
          {qualified.length === 0 ? (
            <div className="p-8 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
                <svg className="h-6 w-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <p className="text-sm text-gray-500">
                No matches yet. Click Refresh to find jobs.
              </p>
            </div>
          ) : (
            <>
              {/* Last 7 Days — always visible */}
              <div>
                <div className="sticky top-0 z-10 border-b border-gray-200 bg-gray-50 px-4 py-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Last 7 Days
                    <span className="ml-1.5 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">
                      {recentMatches.length}
                    </span>
                  </h3>
                </div>
                {recentMatches.length > 0 ? recentMatches.map((match) => (
                  <MatchCard key={match.id} match={match} isSelected={selectedMatchId === match.id} onSelect={setSelectedMatchId} formatSalary={formatSalary} getTimeAgo={getTimeAgo} />
                )) : (
                  <div className="px-4 py-6 text-center text-sm text-gray-400">No recent matches above {SCORE_THRESHOLD}%</div>
                )}
              </div>

              {/* Older */}
              {olderMatches.length > 0 && (
                <div>
                  <button
                    type="button"
                    onClick={() => setOlderExpanded((v) => !v)}
                    className="sticky top-0 z-10 flex w-full items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2 text-left hover:bg-gray-100"
                  >
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Older
                      <span className="ml-1.5 rounded-full bg-gray-200 px-1.5 py-0.5 text-xs font-medium text-gray-600">
                        {olderMatches.length}
                      </span>
                    </h3>
                    <svg className={`h-4 w-4 text-gray-400 transition-transform ${olderExpanded ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {olderExpanded && olderMatches.map((match) => (
                    <MatchCard key={match.id} match={match} isSelected={selectedMatchId === match.id} onSelect={setSelectedMatchId} formatSalary={formatSalary} getTimeAgo={getTimeAgo} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Right column - Job details */}
        <div className="relative flex min-w-0 flex-1 flex-col">
          {selectedMatch ? (
            <>
              {/* Scrollable content */}
              <div className="flex-1 overflow-y-auto">
                <div className="p-6">
                  {/* Interview Probability - Primary Score */}
                  <div className="mb-4 rounded-lg border border-green-200 bg-gradient-to-r from-green-50 to-emerald-50 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-3xl font-bold text-green-700">
                            {selectedMatch.interview_probability ?? selectedMatch.offer_probability}%
                          </span>
                          <div className="flex flex-col">
                            <span className="text-sm font-semibold text-green-800">Interview Probability</span>
                            {selectedMatch.referred && (
                              <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-600">
                                <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                8x Referred Boost
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Referral Toggle */}
                      <ReferralToggle
                        key={`referral-${selectedMatch.id}`}
                        matchId={selectedMatch.id}
                        referred={selectedMatch.referred ?? false}
                        onReferralChange={(data) => {
                          setMatches((current) =>
                            current.map((m) =>
                              m.id === selectedMatch.id
                                ? { ...m, referred: data.referred, interview_probability: data.interview_probability }
                                : m
                            )
                          );
                        }}
                      />
                    </div>

                    {/* Component Scores */}
                    <div className="mt-3 flex flex-wrap gap-2 border-t border-green-200 pt-3">
                      <div className="flex items-center gap-1.5 rounded-md bg-blue-100 px-2.5 py-1">
                        <span className="text-sm font-bold text-blue-700">{selectedMatch.resume_score ?? "--"}</span>
                        <span className="text-xs text-blue-600">Resume</span>
                      </div>
                      <div className="flex items-center gap-1.5 rounded-md bg-purple-100 px-2.5 py-1">
                        <span className="text-sm font-bold text-purple-700">{selectedMatch.cover_letter_score ?? "--"}</span>
                        <span className="text-xs text-purple-600">Cover Letter</span>
                      </div>
                      <div className="flex items-center gap-1.5 rounded-md bg-amber-100 px-2.5 py-1">
                        <span className="text-sm font-bold text-amber-700">{selectedMatch.application_logistics_score ?? "--"}</span>
                        <span className="text-xs text-amber-600">Timing</span>
                      </div>
                      <div className="flex items-center gap-1.5 rounded-md bg-green-100 px-2.5 py-1">
                        <span className="text-sm font-bold text-green-700">{selectedMatch.match_score}</span>
                        <span className="text-xs text-green-600">Match</span>
                      </div>
                    </div>

                    {/* Disclaimer */}
                    <p className="mt-2 text-xs text-gray-500">
                      *Interview Probability is a heuristic estimate based on resume fit, application materials, and timing. It is not a guarantee.
                    </p>
                  </div>

                  {/* IPS Tip */}
                  <CollapsibleTip title="How is Interview Probability calculated?">
                    <p className="mb-2">
                      Interview Probability (IPS) combines four signals to estimate your chances of landing an interview:
                    </p>
                    <ul className="list-disc space-y-1 pl-5">
                      <li><strong>Resume Score</strong> — How well your tailored resume matches the job requirements</li>
                      <li><strong>Cover Letter Score</strong> — Strength of your personalized cover letter</li>
                      <li><strong>Timing Score</strong> — How early you apply relative to the posting date (earlier = better)</li>
                      <li><strong>Match Score</strong> — Skills alignment, title fit, location, and salary compatibility</li>
                    </ul>
                    <p className="mt-2">
                      Marking a referral adds an <strong>8x multiplier</strong> — referrals are the single biggest factor in getting interviews.
                    </p>
                  </CollapsibleTip>

                  {/* Job header */}
                  <div className="rounded-lg border border-gray-200 bg-white p-5">
                    <div className="flex gap-4">
                      {/* Company logo */}
                      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white">
                        {selectedMatch.job.company_logo ? (
                          <img
                            src={selectedMatch.job.company_logo}
                            alt={selectedMatch.job.company}
                            className="h-10 w-10 object-contain"
                          />
                        ) : (
                          <span className="text-xl font-bold text-gray-300">
                            {selectedMatch.job.company.charAt(0)}
                          </span>
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <h2 className="text-xl font-bold text-gray-900">
                          {selectedMatch.job.title}
                        </h2>
                        <p className="text-base text-gray-700">{selectedMatch.job.company}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-600">
                          <span className="inline-flex items-center gap-1">
                            <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            {selectedMatch.job.location}
                          </span>
                          {selectedMatch.job.job_type && (
                            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                              {selectedMatch.job.job_type}
                            </span>
                          )}
                          {formatSalary(selectedMatch.job) && (
                            <span className="font-medium text-green-700">
                              {formatSalary(selectedMatch.job)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Action button + status */}
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <a
                          href={selectedMatch.job.url}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-md bg-green-600 px-4 py-2 text-center text-sm font-semibold text-white shadow-sm hover:bg-green-700"
                        >
                          Apply Now
                        </a>
                        <ApplicationStatusSelect
                          key={`status-${selectedMatch.id}`}
                          matchId={selectedMatch.id}
                          currentStatus={selectedMatch.application_status ?? null}
                          onStatusChange={(newStatus) => {
                            setMatches((current) =>
                              current.map((m) =>
                                m.id === selectedMatch.id
                                  ? { ...m, application_status: newStatus || null }
                                  : m
                              )
                            );
                          }}
                        />
                      </div>
                    </div>

                    {/* Dates row */}
                    <div className="mt-4 flex gap-4 border-t border-gray-100 pt-3 text-sm">
                      {selectedMatch.job.posted_date && (
                        <div className="flex items-center gap-1.5 text-gray-600">
                          <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          Posted {getTimeAgo(selectedMatch.job.posted_date)}
                        </div>
                      )}
                      {selectedMatch.job.application_deadline && (
                        <div className="flex items-center gap-1.5 text-red-600">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Closes {new Date(selectedMatch.job.application_deadline).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Skills section */}
                  {(selectedMatch.reasons.matched_skills?.length || selectedMatch.reasons.missing_skills?.length || selectedMatch.job.required_skills?.length) && (
                    <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
                      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                        Skills Analysis
                      </h3>

                      {selectedMatch.reasons.matched_skills && selectedMatch.reasons.matched_skills.length > 0 && (
                        <div className="mb-4">
                          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-green-700">
                            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            Your Matched Skills
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {selectedMatch.reasons.matched_skills.map((skill, i) => (
                              <span
                                key={i}
                                className="rounded-full border border-green-200 bg-green-50 px-3 py-1 text-sm text-green-700"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {selectedMatch.reasons.missing_skills && selectedMatch.reasons.missing_skills.length > 0 && (
                        <div className="mb-4">
                          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-700">
                            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                            Skills to Highlight
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {selectedMatch.reasons.missing_skills.map((skill, i) => (
                              <span
                                key={i}
                                className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-sm text-amber-700"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {selectedMatch.job.required_skills && selectedMatch.job.required_skills.length > 0 && (
                        <div>
                          <p className="mb-2 text-sm font-medium text-gray-700">
                            Required Skills
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {selectedMatch.job.required_skills.map((skill, i) => (
                              <span
                                key={i}
                                className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-sm text-gray-600"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Job description */}
                  <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                      Job Description
                    </h3>
                    <JobDescription text={selectedMatch.job.description_text} html={selectedMatch.job.description_html} />
                  </div>

                  {/* Bottom padding for sticky bar */}
                  <div className="h-24"></div>
                </div>
              </div>

              {/* Sticky bottom action bar */}
              <div className="absolute bottom-0 left-0 right-0 border-t border-gray-200 bg-white px-6 py-3 shadow-lg">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => handlePrepare(selectedMatch.job.id)}
                    disabled={preparingJobId === selectedMatch.job.id}
                    className="relative overflow-hidden rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800 disabled:cursor-not-allowed"
                  >
                    {preparingJobId === selectedMatch.job.id && prepareProg.isActive && (
                      <span
                        className="absolute inset-y-0 left-0 bg-gray-700 transition-all duration-200"
                        style={{ width: `${prepareProg.progress}%` }}
                      />
                    )}
                    <span className="relative">
                      {preparingJobId === selectedMatch.job.id
                        ? `Preparing... ${prepareProg.pct}%`
                        : "Prepare Materials"}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCreateDraft(selectedMatch)}
                    disabled={creatingDraftId === selectedMatch.id}
                    className="relative overflow-hidden rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed"
                  >
                    {creatingDraftId === selectedMatch.id && draftProg.isActive && (
                      <span
                        className="absolute inset-y-0 left-0 bg-blue-500 transition-all duration-200"
                        style={{ width: `${draftProg.progress}%` }}
                      />
                    )}
                    <span className="relative">
                      {creatingDraftId === selectedMatch.id
                        ? `Creating... ${draftProg.pct}%`
                        : "Create Draft"}
                    </span>
                  </button>

                  {statusByJob[selectedMatch.job.id] && (
                    <span className="text-sm text-gray-600">
                      {statusByJob[selectedMatch.job.id]}
                    </span>
                  )}
                  {draftStatusByMatch[selectedMatch.id] && (
                    <span className="text-sm text-blue-600">
                      {draftStatusByMatch[selectedMatch.id]}
                    </span>
                  )}

                  {linksByJob[selectedMatch.job.id] && (
                    <div className="ml-auto flex gap-2">
                      {linksByJob[selectedMatch.job.id].resume && (
                        <a
                          href={`${API_BASE}${linksByJob[selectedMatch.job.id].resume}`}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                        >
                          Resume
                        </a>
                      )}
                      {linksByJob[selectedMatch.job.id].cover && (
                        <a
                          href={`${API_BASE}${linksByJob[selectedMatch.job.id].cover}`}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                        >
                          Cover Letter
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
                  </svg>
                </div>
                <p className="text-sm text-gray-500">Select a job to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </CandidateLayout>
  );
}

export default function MatchesPage() {
  return (
    <Suspense>
      <MatchesPageContent />
    </Suspense>
  );
}
