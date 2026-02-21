"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Candidate = {
  user_id: number;
  full_name: string | null;
  email: string | null;
  trust_status: string | null;
};

type JobResponse = {
  id: number;
  title: string;
  company: string;
  location: string | null;
  posted_at: string | null;
  sources: string[] | null;
};

type MatchResponse = {
  id: number;
  job: JobResponse;
  match_score: number;
  interview_probability: number | null;
  resume_score: number | null;
  cover_letter_score: number | null;
  application_logistics_score: number | null;
  application_status: string | null;
  reasons: Record<string, unknown>;
  created_at: string;
};

type DocumentResponse = {
  id: number;
  job_id: number;
  job_title: string;
  company: string;
  resume_url: string;
  cover_letter_url: string;
  created_at: string;
  has_active_match: boolean;
};

const TrustBadge = ({ status }: { status: string | null }) => {
  if (!status) return <span className="text-slate-400">None</span>;
  const colors: Record<string, string> = {
    allowed: "bg-emerald-100 text-emerald-700 border-emerald-200",
    soft_quarantine: "bg-amber-100 text-amber-700 border-amber-200",
    hard_quarantine: "bg-red-100 text-red-700 border-red-200",
  };
  const labels: Record<string, string> = {
    allowed: "Allowed",
    soft_quarantine: "Soft Q",
    hard_quarantine: "Hard Q",
  };
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colors[status] || "bg-slate-100 text-slate-600"}`}
    >
      {labels[status] || status}
    </span>
  );
};

const formatDate = (iso: string | null): string => {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
};

export default function CandidateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.userId as string;

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [matches, setMatches] = useState<MatchResponse[]>([]);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"matches" | "documents">(
    "matches",
  );
  const [expandedMatchId, setExpandedMatchId] = useState<number | null>(null);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [candidatesRes, matchesRes, documentsRes] = await Promise.all([
          fetch(`${API_BASE}/api/admin/candidates`, {
            credentials: "include",
          }),
          fetch(`${API_BASE}/api/admin/candidates/${userId}/matches`, {
            credentials: "include",
          }),
          fetch(`${API_BASE}/api/admin/candidates/${userId}/documents`, {
            credentials: "include",
          }),
        ]);

        if (
          candidatesRes.status === 401 ||
          matchesRes.status === 401 ||
          documentsRes.status === 401
        ) {
          router.push("/login");
          return;
        }
        if (
          candidatesRes.status === 403 ||
          matchesRes.status === 403 ||
          documentsRes.status === 403
        ) {
          setError("Admin access required.");
          setIsLoading(false);
          return;
        }

        if (!candidatesRes.ok || !matchesRes.ok || !documentsRes.ok) {
          throw new Error("Failed to load candidate data.");
        }

        const allCandidates = (await candidatesRes.json()) as Candidate[];
        const found = allCandidates.find(
          (c) => c.user_id === Number(userId),
        );
        setCandidate(found || null);

        setMatches((await matchesRes.json()) as MatchResponse[]);
        setDocuments((await documentsRes.json()) as DocumentResponse[]);
      } catch (caught) {
        const message =
          caught instanceof Error
            ? caught.message
            : "Failed to load candidate data.";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    };

    void fetchAll();
  }, [userId, router]);

  // Summary stats
  const totalMatches = matches.length;
  const avgInterview =
    totalMatches > 0
      ? Math.round(
          matches.reduce(
            (sum, m) => sum + (m.interview_probability || 0),
            0,
          ) / totalMatches,
        )
      : 0;

  if (isLoading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
        <h1 className="text-3xl font-semibold">Candidate Detail</h1>
        <p className="text-sm text-slate-600">Loading...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
      {/* Back link + header */}
      <div>
        <Link
          href="/admin/candidates"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; All Candidates
        </Link>
      </div>

      <header className="flex items-center gap-4">
        <div>
          <h1 className="text-3xl font-semibold">
            {candidate?.full_name || "Unknown Candidate"}
          </h1>
          <p className="text-sm text-slate-600">
            {candidate?.email || `User #${userId}`}
          </p>
        </div>
        {candidate && (
          <TrustBadge status={candidate.trust_status} />
        )}
      </header>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setActiveTab("matches")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "matches"
              ? "border-b-2 border-slate-900 text-slate-900"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          Matches ({totalMatches})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("documents")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "documents"
              ? "border-b-2 border-slate-900 text-slate-900"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          Documents ({documents.length})
        </button>
      </div>

      {/* Matches tab */}
      {activeTab === "matches" && (
        <div className="flex flex-col gap-4">
          {/* Summary bar */}
          <div className="flex gap-6 rounded-xl border border-slate-200 bg-slate-50 px-6 py-3 text-sm">
            <span>
              <span className="font-semibold text-slate-900">
                {totalMatches}
              </span>{" "}
              <span className="text-slate-500">matches</span>
            </span>
            <span>
              <span className="font-semibold text-slate-900">
                {avgInterview}%
              </span>{" "}
              <span className="text-slate-500">avg interview probability</span>
            </span>
          </div>

          {/* Matches table */}
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Job Title
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Company
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Location
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Interview %
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Match Score
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Status
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Skills
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                    Posted
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {matches.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center text-slate-500"
                    >
                      No matches found.
                    </td>
                  </tr>
                ) : (
                  matches.map((match) => {
                    const reasons = match.reasons || {};
                    const matchedSkills = (reasons.matched_skills as string[]) || [];
                    const isExpanded = expandedMatchId === match.id;

                    return (
                      <MatchRow
                        key={match.id}
                        match={match}
                        matchedSkills={matchedSkills}
                        isExpanded={isExpanded}
                        onToggle={() =>
                          setExpandedMatchId(isExpanded ? null : match.id)
                        }
                      />
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Documents tab */}
      {activeTab === "documents" && (
        <div className="flex flex-col gap-4">
          {documents.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">
              No tailored documents found.
            </p>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">
                      {doc.job_title}
                    </span>
                    <span className="text-slate-500">&mdash;</span>
                    <span className="text-slate-600">{doc.company}</span>
                    {doc.has_active_match && (
                      <span className="rounded-full border border-emerald-200 bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                        Active Match
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-400">
                    Created {formatDate(doc.created_at)}
                  </span>
                </div>
                <div className="flex gap-2">
                  <a
                    href={`${API_BASE}${doc.resume_url}`}
                    download
                    className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Resume
                  </a>
                  <a
                    href={`${API_BASE}${doc.cover_letter_url}`}
                    download
                    className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Cover Letter
                  </a>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </main>
  );
}

/* ---------- Match row with expandable detail ---------- */

function MatchRow({
  match,
  matchedSkills,
  isExpanded,
  onToggle,
}: {
  match: MatchResponse;
  matchedSkills: string[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const reasons = match.reasons || {};
  const missingSkills = (reasons.missing_skills as string[]) || [];
  const highlightSkills = (reasons.skills_to_highlight as string[]) || [];
  const requiredGap = (reasons.required_skills_missing as string[]) || [];

  return (
    <>
      <tr
        className="cursor-pointer transition-colors hover:bg-slate-50"
        onClick={onToggle}
      >
        <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
          {match.job.title}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-slate-600">
          {match.job.company}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-slate-600">
          {match.job.location || "\u2014"}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-slate-900 font-medium">
          {match.interview_probability != null
            ? `${match.interview_probability}%`
            : "\u2014"}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-slate-600">
          {match.match_score}
        </td>
        <td className="whitespace-nowrap px-4 py-3">
          {match.application_status ? (
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              {match.application_status}
            </span>
          ) : (
            <span className="text-slate-400">\u2014</span>
          )}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-slate-600">
          {matchedSkills.length}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-slate-600">
          {formatDate(match.job.posted_at)}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={8} className="bg-slate-50 px-6 py-4">
            <div className="flex flex-col gap-4">
              {/* Score breakdown */}
              <div className="flex flex-wrap gap-6 text-sm">
                <ScorePill
                  label="Resume"
                  value={match.resume_score}
                />
                <ScorePill
                  label="Cover Letter"
                  value={match.cover_letter_score}
                />
                <ScorePill
                  label="Timing"
                  value={match.application_logistics_score}
                />
                <ScorePill label="Match" value={match.match_score} />
              </div>

              {/* Skill pills */}
              <div className="flex flex-wrap gap-2">
                {matchedSkills.map((s) => (
                  <SkillPill key={`m-${s}`} skill={s} color="green" />
                ))}
                {missingSkills.map((s) => (
                  <SkillPill key={`x-${s}`} skill={s} color="amber" />
                ))}
                {highlightSkills.map((s) => (
                  <SkillPill key={`h-${s}`} skill={s} color="blue" />
                ))}
                {requiredGap.map((s) => (
                  <SkillPill key={`r-${s}`} skill={s} color="red" />
                ))}
                {matchedSkills.length === 0 &&
                  missingSkills.length === 0 &&
                  highlightSkills.length === 0 &&
                  requiredGap.length === 0 && (
                    <span className="text-xs text-slate-400">
                      No skill data available
                    </span>
                  )}
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
                  Matched
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-amber-400" />
                  Missing
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-blue-400" />
                  Highlight
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
                  Required Gap
                </span>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ScorePill({
  label,
  value,
}: {
  label: string;
  value: number | null | undefined;
}) {
  return (
    <span className="text-slate-600">
      <span className="font-medium text-slate-900">
        {value != null ? value : "\u2014"}
      </span>{" "}
      {label}
    </span>
  );
}

function SkillPill({ skill, color }: { skill: string; color: string }) {
  const colors: Record<string, string> = {
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    red: "border-red-200 bg-red-50 text-red-700",
  };
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colors[color]}`}
    >
      {skill}
    </span>
  );
}
