"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import CandidateLayout from "../../../components/CandidateLayout";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ChangeEntry = {
  section?: string;
  company?: string;
  bullet_index?: number;
  type?: string;
  change?: string;
  description?: string;
  original?: string;
  modified?: string;
  reason?: string;
};

type KeywordAlignment = {
  matched_keywords?: string[];
  gap_keywords?: string[];
  added_to_resume?: string[];
  match_rate_before?: number;
  match_rate_after?: number;
};

type GroundingValidation = {
  employers_verified?: boolean;
  titles_verified?: boolean;
  dates_verified?: boolean;
  education_verified?: boolean;
  certifications_verified?: boolean;
  hallucinations_detected?: number;
};

type ChangeLog = {
  summary?: string;
  changes?: ChangeEntry[];
  keyword_alignment?: KeywordAlignment;
  grounding_validation?: GroundingValidation;
  job_title?: string;
  cover_letter_score?: number;
  matched_skills?: string[];
};

type TailorDetail = {
  id: number;
  job_id: number;
  job_title: string;
  company: string;
  profile_version: number;
  resume_url: string;
  cover_letter_url: string;
  created_at: string;
  change_log: ChangeLog | null;
};

export default function TailoredResumePage() {
  const params = useParams();
  const router = useRouter();
  const matchId = params.matchId as string;

  const [detail, setDetail] = useState<TailorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDetail = async () => {
      try {
        // First, find the tailored resume for this match's job
        // We need to get documents and find the one matching this job
        const docsResponse = await fetch(
          `${API_BASE}/api/tailor/documents`,
          { credentials: "include" }
        );
        if (!docsResponse.ok) {
          throw new Error("Failed to load documents.");
        }
        const docs = (await docsResponse.json()) as Array<{
          id: number;
          job_id: number;
        }>;

        // We need to find the match to get job_id, then find the doc
        const matchesResponse = await fetch(`${API_BASE}/api/matches/all`, {
          credentials: "include",
        });
        if (!matchesResponse.ok) {
          throw new Error("Failed to load matches.");
        }
        const matches = (await matchesResponse.json()) as Array<{
          id: number;
          job: { id: number };
        }>;
        const match = matches.find((m) => m.id === Number(matchId));
        if (!match) {
          throw new Error("Match not found.");
        }

        // Find the most recent tailored doc for this job
        const doc = docs.find((d) => d.job_id === match.job.id);
        if (!doc) {
          throw new Error(
            "No tailored resume found for this match. Generate one first."
          );
        }

        // Fetch the detail
        const detailResponse = await fetch(
          `${API_BASE}/api/tailor/detail/${doc.id}`,
          { credentials: "include" }
        );
        if (!detailResponse.ok) {
          throw new Error("Failed to load tailored resume details.");
        }
        const detailData = (await detailResponse.json()) as TailorDetail;
        setDetail(detailData);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    void loadDetail();
  }, [matchId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="mx-auto max-w-4xl">
          <div className="animate-pulse space-y-4">
            <div className="h-8 w-48 rounded bg-gray-200" />
            <div className="h-6 w-96 rounded bg-gray-200" />
            <div className="h-40 rounded bg-gray-200" />
            <div className="h-40 rounded bg-gray-200" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="mx-auto max-w-4xl">
          <Link
            href="/matches"
            className="mb-4 inline-block text-sm text-green-700 hover:underline"
          >
            &larr; Back to Matches
          </Link>
          <div className="rounded-lg border border-red-200 bg-red-50 p-6">
            <p className="text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!detail) return null;

  const changeLog = detail.change_log;
  const changes = changeLog?.changes ?? [];
  const keywords = changeLog?.keyword_alignment;
  const grounding = changeLog?.grounding_validation;

  return (
    <CandidateLayout>
      <div>
        {/* Back link */}
        <Link
          href="/matches"
          className="mb-4 inline-block text-sm text-green-700 hover:underline"
        >
          &larr; Back to Matches
        </Link>

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Tailored Resume for {detail.job_title}
          </h1>
          <p className="mt-1 text-gray-600">
            at {detail.company} &mdash; Generated{" "}
            {new Date(detail.created_at).toLocaleDateString()}
          </p>
        </div>

        {/* Download buttons */}
        <div className="mb-8 flex flex-wrap gap-3">
          <a
            href={`${API_BASE}${detail.resume_url}`}
            className="inline-flex items-center rounded-lg bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800"
          >
            Download Resume DOCX
          </a>
          <a
            href={`${API_BASE}${detail.cover_letter_url}`}
            className="inline-flex items-center rounded-lg border border-green-700 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-50"
          >
            Download Cover Letter DOCX
          </a>
        </div>

        {/* What Changed section */}
        {changeLog?.summary && (
          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2">
              What Changed
            </h2>
            <p className="mb-4 text-sm text-gray-700 bg-gray-100 rounded-lg p-3">
              {changeLog.summary}
            </p>

            {changes.length > 0 && (
              <div className="space-y-3">
                {changes.map((change, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-gray-200 bg-white p-4"
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                        {change.section || "general"}
                      </span>
                      {change.company && (
                        <span className="text-sm font-medium text-gray-700">
                          {change.company}
                        </span>
                      )}
                      {change.type && (
                        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                          {change.type}
                        </span>
                      )}
                    </div>
                    {change.description && (
                      <p className="text-sm text-gray-700">
                        {change.description}
                      </p>
                    )}
                    {change.change && (
                      <p className="text-sm text-gray-700">{change.change}</p>
                    )}
                    {change.original && (
                      <div className="mt-2 rounded bg-red-50 p-2">
                        <p className="text-xs font-medium text-red-600">
                          Original:
                        </p>
                        <p className="text-sm text-red-800">
                          {change.original}
                        </p>
                      </div>
                    )}
                    {change.modified && (
                      <div className="mt-2 rounded bg-green-50 p-2">
                        <p className="text-xs font-medium text-green-600">
                          Modified:
                        </p>
                        <p className="text-sm text-green-800">
                          {change.modified}
                        </p>
                      </div>
                    )}
                    {change.reason && (
                      <p className="mt-2 text-xs italic text-gray-500">
                        Reason: {change.reason}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Keyword Alignment section */}
        {keywords && (
          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2">
              Keyword Alignment
            </h2>
            <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
              {keywords.matched_keywords &&
                keywords.matched_keywords.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-green-700 mb-1">
                      Matched Keywords
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {keywords.matched_keywords.map((kw, i) => (
                        <span
                          key={i}
                          className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

              {keywords.gap_keywords && keywords.gap_keywords.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-amber-700 mb-1">
                    Gaps (you don&apos;t have these &mdash; consider upskilling)
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {keywords.gap_keywords.map((kw, i) => (
                      <span
                        key={i}
                        className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {keywords.added_to_resume &&
                keywords.added_to_resume.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-blue-700 mb-1">
                      Keywords Added to Resume
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {keywords.added_to_resume.map((kw, i) => (
                        <span
                          key={i}
                          className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

              {keywords.match_rate_before != null &&
                keywords.match_rate_after != null && (
                  <div className="rounded-lg bg-gray-50 p-3">
                    <p className="text-sm font-medium text-gray-700">
                      Match Rate:{" "}
                      <span className="text-gray-500">
                        {keywords.match_rate_before}%
                      </span>
                      <span className="mx-2 text-gray-400">&rarr;</span>
                      <span className="font-bold text-green-700">
                        {keywords.match_rate_after}%
                      </span>
                    </p>
                  </div>
                )}
            </div>
          </section>
        )}

        {/* Grounding Verification section */}
        {grounding && (
          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2">
              Grounding Verification
            </h2>
            <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2">
              <VerificationRow
                label="All employers verified"
                verified={grounding.employers_verified}
              />
              <VerificationRow
                label="All titles verified"
                verified={grounding.titles_verified}
              />
              <VerificationRow
                label="All dates verified"
                verified={grounding.dates_verified}
              />
              <VerificationRow
                label="All education verified"
                verified={grounding.education_verified}
              />
              <VerificationRow
                label="All certifications verified"
                verified={grounding.certifications_verified}
              />
              {grounding.hallucinations_detected != null && (
                <div className="pt-2 border-t border-gray-100">
                  <p className="text-sm text-gray-600">
                    Hallucinations detected:{" "}
                    <span
                      className={
                        grounding.hallucinations_detected === 0
                          ? "font-bold text-green-700"
                          : "font-bold text-red-600"
                      }
                    >
                      {grounding.hallucinations_detected}
                    </span>
                  </p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Cover letter score if available */}
        {changeLog?.cover_letter_score != null && (
          <section className="mb-8">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-sm text-gray-600">
                Cover Letter Quality Score:{" "}
                <span className="text-lg font-bold text-green-700">
                  {changeLog.cover_letter_score}/100
                </span>
              </p>
            </div>
          </section>
        )}
      </div>
    </CandidateLayout>
  );
}

function VerificationRow({
  label,
  verified,
}: {
  label: string;
  verified?: boolean;
}) {
  if (verified == null) return null;
  return (
    <div className="flex items-center gap-2">
      <span
        className={`text-lg ${verified ? "text-green-600" : "text-red-500"}`}
      >
        {verified ? "\u2705" : "\u274C"}
      </span>
      <span className="text-sm text-gray-700">{label}</span>
    </div>
  );
}
