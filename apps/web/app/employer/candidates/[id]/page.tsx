"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface CandidateDetail {
  id: number;
  name: string;
  headline?: string;
  profile_json?: Record<string, unknown>;
  years_experience: number | null;
  skills?: string[];
  experience?: Record<string, unknown>[];
  education?: Record<string, unknown>[];
  anonymized: boolean;
}

interface EmployerJob {
  id: number;
  title: string;
  status: string;
}

export default function CandidateProfilePage() {
  const params = useParams();
  const candidateId = params.id as string;

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notes, setNotes] = useState("");

  // Introduction state
  const [introMessage, setIntroMessage] = useState("");
  const [introJobId, setIntroJobId] = useState<number | null>(null);
  const [introSending, setIntroSending] = useState(false);
  const [introSent, setIntroSent] = useState(false);
  const [introError, setIntroError] = useState<string | null>(null);
  const [employerJobs, setEmployerJobs] = useState<EmployerJob[]>([]);

  useEffect(() => {
    async function fetchCandidate() {
      try {
        const res = await fetch(
          `${API_BASE}/api/employer/candidates/${candidateId}`,
          { credentials: "include" },
        );
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || "Candidate not found");
        }
        setCandidate(await res.json());
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load candidate",
        );
      } finally {
        setIsLoading(false);
      }
    }
    fetchCandidate();
  }, [candidateId]);

  // Fetch employer's active jobs for the intro dropdown
  useEffect(() => {
    async function fetchJobs() {
      try {
        const res = await fetch(
          `${API_BASE}/api/employer/jobs?status=active&limit=50`,
          { credentials: "include" },
        );
        if (res.ok) {
          const data = await res.json();
          setEmployerJobs(data.jobs || data || []);
        }
      } catch {
        // Non-critical, ignore
      }
    }
    fetchJobs();
  }, []);

  async function saveCandidate() {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/employer/candidates/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          candidate_id: parseInt(candidateId),
          notes: notes || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to save candidate");
      }
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function sendIntroduction() {
    if (introMessage.length < 20) {
      setIntroError("Message must be at least 20 characters.");
      return;
    }
    setIntroSending(true);
    setIntroError(null);
    try {
      const res = await fetch(`${API_BASE}/api/employer/introductions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          candidate_profile_id: parseInt(candidateId),
          employer_job_id: introJobId,
          message: introMessage,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(
          data?.detail || "Failed to send introduction request",
        );
      }
      setIntroSent(true);
    } catch (err) {
      setIntroError(
        err instanceof Error ? err.message : "Failed to send introduction",
      );
    } finally {
      setIntroSending(false);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
        <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />
      </div>
    );
  }

  if (error && !candidate) {
    return (
      <div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
        <Link
          href="/employer/candidates"
          className="mt-4 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          &larr; Back to Search
        </Link>
      </div>
    );
  }

  if (!candidate) return null;

  const pj = candidate.profile_json || {};
  const basics = (pj.basics as Record<string, unknown>) || {};
  const skills = (candidate.skills ||
    (pj.skills as string[]) ||
    []) as string[];
  const experience = (candidate.experience ||
    (pj.experience as Record<string, unknown>[]) ||
    []) as Record<string, unknown>[];
  const education = (candidate.education ||
    (pj.education as Record<string, unknown>[]) ||
    []) as Record<string, unknown>[];
  const preferences = (pj.preferences as Record<string, unknown>) || {};
  const preferredLocations = (preferences.locations as string[]) || [];
  const remoteOk = preferences.remote_ok as boolean | null | undefined;
  const remotePreference = basics.remote_preference as string | null | undefined;
  const willingToRelocate = basics.willing_to_relocate as boolean | null | undefined;
  const currentLocation = basics.location as string | undefined;

  return (
    <div>
      <Link
        href="/employer/candidates"
        className="mb-4 inline-block text-sm text-slate-500 hover:text-slate-700"
      >
        &larr; Back to Search
      </Link>

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            {candidate.name}
          </h1>
          {candidate.anonymized && (
            <span className="mt-1 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
              Anonymous profile
            </span>
          )}
          {candidate.years_experience != null && (
            <p className="mt-1 text-sm text-slate-500">
              {candidate.years_experience} years of experience
            </p>
          )}
          {!candidate.anonymized && !!basics.location && (
            <p className="text-sm text-slate-500">
              {basics.location as string}
            </p>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Main content */}
        <div className="space-y-6 lg:col-span-2">
          {/* Experience */}
          {experience.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-slate-900">
                Experience
              </h2>
              <div className="space-y-4">
                {experience.map((exp, i) => (
                  <div
                    key={i}
                    className="border-l-2 border-slate-200 pl-4"
                  >
                    <p className="font-medium text-slate-900">
                      {(exp.title as string) || "Unknown Role"}
                    </p>
                    {!!exp.company && (
                      <p className="text-sm text-slate-600">
                        {exp.company as string}
                      </p>
                    )}
                    {!!(exp.start_date || exp.end_date) && (
                      <p className="text-xs text-slate-400">
                        {(exp.start_date as string) || "?"} &ndash;{" "}
                        {(exp.end_date as string) || "Present"}
                      </p>
                    )}
                    {!!exp.description && (
                      <p className="mt-1 text-sm text-slate-500">
                        {exp.description as string}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Skills */}
          {skills.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-slate-900">
                Skills
              </h2>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill, i) => (
                  <span
                    key={i}
                    className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700"
                  >
                    {typeof skill === "string" ? skill : String(skill)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Education */}
          {education.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-slate-900">
                Education
              </h2>
              <div className="space-y-3">
                {education.map((edu, i) => (
                  <div key={i} className="border-l-2 border-slate-200 pl-4">
                    <p className="font-medium text-slate-900">
                      {(edu.degree as string) || (edu.field as string) || "Degree"}
                    </p>
                    {!!edu.institution && (
                      <p className="text-sm text-slate-600">
                        {edu.institution as string}
                      </p>
                    )}
                    {!!edu.year && (
                      <p className="text-xs text-slate-400">
                        {edu.year as string}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Save Candidate card */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 font-semibold text-slate-900">
              Save Candidate
            </h3>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="Add notes..."
            />
            <button
              onClick={saveCandidate}
              disabled={saving || saved}
              className="mt-3 w-full rounded-md bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {saved ? "Saved" : saving ? "Saving..." : "Save Candidate"}
            </button>
          </div>

          {/* Send Introduction card */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 font-semibold text-slate-900">
              Send Introduction
            </h3>

            {introSent ? (
              <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
                Introduction sent! The candidate will be notified and can choose
                to share their contact information.
              </div>
            ) : (
              <>
                {/* Optional job selector */}
                {employerJobs.length > 0 && (
                  <div className="mb-3">
                    <label className="mb-1 block text-xs font-medium text-slate-600">
                      Related job (optional)
                    </label>
                    <select
                      value={introJobId ?? ""}
                      onChange={(e) =>
                        setIntroJobId(
                          e.target.value ? parseInt(e.target.value) : null,
                        )
                      }
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                    >
                      <option value="">No specific job</option>
                      {employerJobs.map((job) => (
                        <option key={job.id} value={job.id}>
                          {job.title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <textarea
                  value={introMessage}
                  onChange={(e) => setIntroMessage(e.target.value)}
                  rows={4}
                  maxLength={1000}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="Introduce yourself and explain why this candidate is a good fit..."
                />
                <div className="mt-1 flex justify-between text-xs text-slate-400">
                  <span>
                    {introMessage.length < 20
                      ? `${20 - introMessage.length} more chars needed`
                      : ""}
                  </span>
                  <span>{introMessage.length}/1000</span>
                </div>

                {introError && (
                  <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {introError}
                  </div>
                )}

                <button
                  onClick={sendIntroduction}
                  disabled={introSending || introMessage.length < 20}
                  className="mt-3 w-full rounded-md bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {introSending ? "Sending..." : "Send Introduction"}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
