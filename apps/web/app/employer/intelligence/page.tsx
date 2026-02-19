"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface CandidateOption {
  id: number;
  name: string;
}

interface JobOption {
  id: number;
  title: string;
}

export default function IntelligenceDashboard() {
  // Lookup data loaded on mount
  const [candidates, setCandidates] = useState<CandidateOption[]>([]);
  const [jobs, setJobs] = useState<JobOption[]>([]);

  // Brief generator state
  const [briefCandidateId, setBriefCandidateId] = useState("");
  const [briefJobId, setBriefJobId] = useState("");
  const [briefType, setBriefType] = useState("general");
  const [briefResult, setBriefResult] = useState<Record<string, unknown> | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);

  // Salary intelligence state
  const [salaryRole, setSalaryRole] = useState("");
  const [salaryLocation, setSalaryLocation] = useState("");
  const [salaryResult, setSalaryResult] = useState<Record<string, unknown> | null>(null);
  const [salaryLoading, setSalaryLoading] = useState(false);

  // Time-to-fill state
  const [ttfJobId, setTtfJobId] = useState("");
  const [ttfResult, setTtfResult] = useState<Record<string, unknown> | null>(null);
  const [ttfLoading, setTtfLoading] = useState(false);

  // Market position state
  const [mpCandidateId, setMpCandidateId] = useState("");
  const [mpJobId, setMpJobId] = useState("");
  const [mpResult, setMpResult] = useState<Record<string, unknown> | null>(null);
  const [mpLoading, setMpLoading] = useState(false);

  const [copied, setCopied] = useState(false);

  // Load saved candidates and jobs on mount
  useEffect(() => {
    fetch(`${API}/api/employer/candidates/saved`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Array<{ candidate_id: number; candidate?: { name?: string } | null }>) => {
        setCandidates(
          list.map((s) => ({
            id: s.candidate_id,
            name: s.candidate?.name || `Candidate ${s.candidate_id}`,
          })),
        );
      })
      .catch(() => {});

    fetch(`${API}/api/employer/jobs`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Array<{ id: number; title?: string }>) => {
        setJobs(
          list.map((j) => ({
            id: j.id,
            title: j.title || `Job ${j.id}`,
          })),
        );
      })
      .catch(() => {});
  }, []);

  async function apiFetch(path: string, options: RequestInit = {}) {
    const res = await fetch(`${API}${path}`, {
      credentials: "include",
      ...options,
    });
    if (!res.ok) {
      let message = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (body.detail) message = String(body.detail);
      } catch {
        // body wasn't JSON — use default message
      }
      throw new Error(message);
    }
    return res.json();
  }

  async function generateBrief() {
    setBriefLoading(true);
    setBriefResult(null);
    try {
      const params = new URLSearchParams({ brief_type: briefType });
      if (briefJobId) params.set("job_id", briefJobId);
      const data = await apiFetch(
        `/api/career-intelligence/brief/${briefCandidateId}?${params}`,
        { method: "POST" }
      );
      setBriefResult(data);
    } catch (e: unknown) {
      setBriefResult({ error: (e as Error).message });
    }
    setBriefLoading(false);
  }

  async function fetchSalary() {
    setSalaryLoading(true);
    setSalaryResult(null);
    try {
      const params = new URLSearchParams({ role: salaryRole });
      if (salaryLocation) params.set("location", salaryLocation);
      const data = await apiFetch(`/api/career-intelligence/salary?${params}`);
      setSalaryResult(data);
    } catch (e: unknown) {
      setSalaryResult({ error: (e as Error).message });
    }
    setSalaryLoading(false);
  }

  async function fetchTimeFill() {
    setTtfLoading(true);
    setTtfResult(null);
    try {
      const data = await apiFetch(
        `/api/career-intelligence/time-to-fill/${ttfJobId}`
      );
      setTtfResult(data);
    } catch (e: unknown) {
      setTtfResult({ error: (e as Error).message });
    }
    setTtfLoading(false);
  }

  async function fetchMarketPosition() {
    setMpLoading(true);
    setMpResult(null);
    try {
      const data = await apiFetch(
        `/api/career-intelligence/market-position/${mpCandidateId}/${mpJobId}`
      );
      setMpResult(data);
    } catch (e: unknown) {
      setMpResult({ error: (e as Error).message });
    }
    setMpLoading(false);
  }

  function copyBrief() {
    if (briefResult && !briefResult.error) {
      const text =
        (briefResult as Record<string, unknown>).full_text ||
        JSON.stringify(briefResult, null, 2);
      navigator.clipboard.writeText(String(text));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  const selectClasses =
    "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm";

  const noCandidates = candidates.length === 0;
  const noJobs = jobs.length === 0;

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-slate-900">
        Career Intelligence
      </h1>
      <p className="mb-8 text-sm text-slate-500">
        AI-powered recruiter tools for candidate evaluation, salary data, and
        hiring predictions.
      </p>

      {noCandidates && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          No saved candidates yet.{" "}
          <a href="/employer/candidates" className="font-medium underline">
            Search and save candidates
          </a>{" "}
          to use the Brief Generator and Market Position tools.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Brief Generator */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Candidate Brief Generator
          </h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Candidate
              </label>
              <select
                value={briefCandidateId}
                onChange={(e) => setBriefCandidateId(e.target.value)}
                className={selectClasses}
                disabled={noCandidates}
              >
                <option value="">
                  {noCandidates
                    ? "No saved candidates"
                    : "Select a candidate..."}
                </option>
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (#{c.id})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Job (optional)
              </label>
              <select
                value={briefJobId}
                onChange={(e) => setBriefJobId(e.target.value)}
                className={selectClasses}
              >
                <option value="">
                  {noJobs ? "No jobs posted" : "None (general brief)"}
                </option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} (#{j.id})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Brief Type
              </label>
              <select
                value={briefType}
                onChange={(e) => setBriefType(e.target.value)}
                className={selectClasses}
              >
                <option value="general">General</option>
                <option value="job_specific">Job-Specific</option>
                <option value="submittal">Submittal (Client-Ready)</option>
              </select>
            </div>
            <button
              onClick={generateBrief}
              disabled={briefLoading || !briefCandidateId}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {briefLoading ? "Generating..." : "Generate Brief"}
            </button>
          </div>
          {briefResult && (
            <div className="mt-4">
              {briefResult.error ? (
                <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
                  {String(briefResult.error)}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">
                      BRIEF RESULT
                    </span>
                    <button
                      onClick={copyBrief}
                      className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600 hover:bg-slate-200"
                    >
                      {copied ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <div className="max-h-[32rem] overflow-auto rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-800">
                    {/* Headline + Score badge */}
                    {briefResult.headline && (
                      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                        <h3 className="text-sm font-bold text-slate-900">
                          {String(briefResult.headline)}
                        </h3>
                        {briefResult.fit_score != null && (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                              Number(briefResult.fit_score) >= 75
                                ? "bg-green-100 text-green-800"
                                : Number(briefResult.fit_score) >= 60
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-red-100 text-red-800"
                            }`}
                          >
                            Fit: {String(briefResult.fit_score)}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Recommended action */}
                    {briefResult.recommended_action && (
                      <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-blue-700">
                        {String(briefResult.recommended_action)}
                      </div>
                    )}

                    {/* Elevator pitch */}
                    {briefResult.elevator_pitch && (
                      <p className="mb-3 italic text-slate-700">
                        {String(briefResult.elevator_pitch)}
                      </p>
                    )}

                    {/* Strengths */}
                    {Array.isArray(briefResult.strengths) &&
                      briefResult.strengths.length > 0 && (
                        <div className="mb-3">
                          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-green-700">
                            Strengths
                          </div>
                          <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-700">
                            {(briefResult.strengths as string[]).map(
                              (s, i) => (
                                <li key={i}>{s}</li>
                              ),
                            )}
                          </ul>
                        </div>
                      )}

                    {/* Concerns */}
                    {Array.isArray(briefResult.concerns) &&
                      briefResult.concerns.length > 0 && (
                        <div className="mb-3">
                          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
                            Concerns
                          </div>
                          <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-700">
                            {(briefResult.concerns as string[]).map(
                              (s, i) => (
                                <li key={i}>{s}</li>
                              ),
                            )}
                          </ul>
                        </div>
                      )}

                    {/* Fit rationale */}
                    {briefResult.fit_rationale && (
                      <div className="mb-3">
                        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Fit Rationale
                        </div>
                        <p className="whitespace-pre-line text-xs text-slate-700">
                          {String(briefResult.fit_rationale)}
                        </p>
                      </div>
                    )}

                    {/* Skills alignment */}
                    {briefResult.skills_alignment && (
                      <div className="mb-3">
                        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Skills Alignment
                        </div>
                        {Array.isArray(
                          (
                            briefResult.skills_alignment as Record<
                              string,
                              unknown
                            >
                          ).matched,
                        ) && (
                          <div className="mb-1 flex flex-wrap gap-1">
                            {(
                              (
                                briefResult.skills_alignment as Record<
                                  string,
                                  unknown
                                >
                              ).matched as Array<{
                                skill: string;
                                evidence?: string;
                              }>
                            ).map((m, i) => (
                              <span
                                key={i}
                                className="inline-flex items-center rounded bg-green-50 px-1.5 py-0.5 text-xs text-green-700"
                                title={m.evidence || ""}
                              >
                                {m.skill}
                              </span>
                            ))}
                          </div>
                        )}
                        {Array.isArray(
                          (
                            briefResult.skills_alignment as Record<
                              string,
                              unknown
                            >
                          ).missing,
                        ) && (
                          <div className="flex flex-wrap gap-1">
                            {(
                              (
                                briefResult.skills_alignment as Record<
                                  string,
                                  unknown
                                >
                              ).missing as Array<{
                                skill: string;
                                severity?: string;
                              }>
                            ).map((m, i) => (
                              <span
                                key={i}
                                className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs ${
                                  m.severity === "required"
                                    ? "bg-red-50 text-red-700"
                                    : "bg-amber-50 text-amber-700"
                                }`}
                              >
                                {m.skill}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Compensation + availability */}
                    {(briefResult.compensation_note ||
                      briefResult.availability) && (
                      <div className="mb-2 flex flex-wrap gap-4 text-xs text-slate-600">
                        {briefResult.compensation_note && (
                          <span>
                            <span className="font-semibold">Comp:</span>{" "}
                            {String(briefResult.compensation_note)}
                          </span>
                        )}
                        {briefResult.availability && (
                          <span>
                            <span className="font-semibold">Availability:</span>{" "}
                            {String(briefResult.availability)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Salary Intelligence */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Salary Intelligence
          </h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Role Title
              </label>
              <input
                type="text"
                value={salaryRole}
                onChange={(e) => setSalaryRole(e.target.value)}
                className={selectClasses}
                placeholder="e.g. Software Engineer"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Location (optional)
              </label>
              <input
                type="text"
                value={salaryLocation}
                onChange={(e) => setSalaryLocation(e.target.value)}
                className={selectClasses}
                placeholder="e.g. San Francisco"
              />
            </div>
            <button
              onClick={fetchSalary}
              disabled={salaryLoading || !salaryRole}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {salaryLoading ? "Loading..." : "Get Salary Data"}
            </button>
          </div>
          {salaryResult && (
            <div className="mt-4">
              {salaryResult.error ? (
                <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
                  {String(salaryResult.error)}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="text-xs font-semibold text-slate-500">
                    SALARY PERCENTILES ({String(salaryResult.sample_size)} samples)
                  </div>
                  {/* CSS-only bar chart */}
                  <div className="space-y-2">
                    {["p10", "p25", "p50", "p75", "p90"].map((p) => {
                      const val = Number(salaryResult[p]) || 0;
                      const maxVal = Number(salaryResult.p90) || 1;
                      const pct = Math.round((val / maxVal) * 100);
                      return (
                        <div key={p} className="flex items-center gap-3">
                          <span className="w-8 text-right text-xs font-mono text-slate-500">
                            {p.toUpperCase()}
                          </span>
                          <div className="relative h-6 flex-1 overflow-hidden rounded bg-slate-100">
                            <div
                              className="h-full rounded bg-blue-600 transition-all duration-500"
                              style={{ width: `${pct}%` }}
                            />
                            <span
                              className={`absolute inset-y-0 right-2 flex items-center text-xs font-semibold ${
                                pct >= 60 ? "text-white" : "text-slate-700"
                              }`}
                            >
                              ${val.toLocaleString()}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Time-to-Fill */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Time-to-Fill Prediction
          </h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Job
              </label>
              <select
                value={ttfJobId}
                onChange={(e) => setTtfJobId(e.target.value)}
                className={selectClasses}
                disabled={noJobs}
              >
                <option value="">
                  {noJobs ? "No jobs posted" : "Select a job..."}
                </option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} (#{j.id})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={fetchTimeFill}
              disabled={ttfLoading || !ttfJobId}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {ttfLoading ? "Predicting..." : "Predict Time-to-Fill"}
            </button>
          </div>
          {ttfResult && (
            <div className="mt-4">
              {ttfResult.error ? (
                <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
                  {String(ttfResult.error)}
                </div>
              ) : (
                <div className="rounded-lg bg-blue-50 p-4">
                  <div className="text-3xl font-bold text-blue-700">
                    {String(ttfResult.predicted_days)} days
                  </div>
                  <div className="mt-1 text-xs text-blue-600">
                    Confidence: {String(Math.round(Number(ttfResult.confidence) * 100))}%
                  </div>
                  {ttfResult.factors && (
                    <div className="mt-3 space-y-1">
                      <div className="text-xs font-semibold text-slate-500">
                        FACTORS
                      </div>
                      {Object.entries(
                        ttfResult.factors as Record<string, number>
                      ).map(([key, val]) => (
                        <div key={key} className="flex justify-between text-xs">
                          <span className="text-slate-600">
                            {key.replace(/_/g, " ")}
                          </span>
                          <span
                            className={
                              val < 0 ? "text-green-600" : "text-red-600"
                            }
                          >
                            {val > 0 ? "+" : ""}
                            {Math.round(val * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Market Position */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">
            Market Position
          </h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Candidate
              </label>
              <select
                value={mpCandidateId}
                onChange={(e) => setMpCandidateId(e.target.value)}
                className={selectClasses}
                disabled={noCandidates}
              >
                <option value="">
                  {noCandidates
                    ? "No saved candidates"
                    : "Select a candidate..."}
                </option>
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (#{c.id})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Job
              </label>
              <select
                value={mpJobId}
                onChange={(e) => setMpJobId(e.target.value)}
                className={selectClasses}
                disabled={noJobs}
              >
                <option value="">
                  {noJobs ? "No jobs posted" : "Select a job..."}
                </option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} (#{j.id})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={fetchMarketPosition}
              disabled={mpLoading || !mpCandidateId || !mpJobId}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mpLoading ? "Loading..." : "Get Market Position"}
            </button>
          </div>
          {mpResult && (
            <div className="mt-4">
              {mpResult.error ? (
                <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
                  {String(mpResult.error)}
                </div>
              ) : mpResult.percentile != null ? (
                <div className="rounded-lg bg-green-50 p-4">
                  <div className="text-3xl font-bold text-green-700">
                    Top {String(100 - Number(mpResult.percentile))}%
                  </div>
                  <div className="mt-1 text-xs text-green-600">
                    Rank #{String(mpResult.rank)} of {String(mpResult.total_candidates)}{" "}
                    candidates
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    Score: {String(mpResult.candidate_score)} (avg:{" "}
                    {String(mpResult.avg_score)})
                  </div>
                </div>
              ) : (
                <div className="rounded-lg bg-yellow-50 p-3 text-xs text-yellow-700">
                  {String(mpResult.message)}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
