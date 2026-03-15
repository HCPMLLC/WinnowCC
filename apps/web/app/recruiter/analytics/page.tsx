"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface FunnelStage {
  stage: string;
  count: number;
}

interface TimeToHire {
  count: number;
  avg_days: number | null;
  median_days: number | null;
  p75_days: number | null;
}

interface Conversion {
  from_stage: string;
  to_stage: string;
  from_count: number;
  to_count: number;
  rate: number;
}

interface SourceRow {
  source: string;
  total: number;
  hired: number;
  hire_rate: number;
}

interface RecruiterJob {
  id: number;
  title: string;
}

const STAGE_COLORS: Record<string, string> = {
  sourced: "bg-slate-200",
  qualified: "bg-blue-200",
  interviewing: "bg-purple-200",
  offered: "bg-emerald-200",
  hired: "bg-green-300",
  rejected: "bg-red-200",
};

const STAGE_TEXT: Record<string, string> = {
  sourced: "text-slate-700",
  qualified: "text-blue-700",
  interviewing: "text-purple-700",
  offered: "text-emerald-700",
  hired: "text-green-700",
  rejected: "text-red-700",
};

export default function RecruiterAnalyticsPage() {
  const [funnel, setFunnel] = useState<FunnelStage[]>([]);
  const [tth, setTth] = useState<TimeToHire | null>(null);
  const [conversions, setConversions] = useState<Conversion[]>([]);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [jobs, setJobs] = useState<RecruiterJob[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [loading, setLoading] = useState(true);

  // Fetch jobs list
  useEffect(() => {
    fetch(`${API_BASE}/api/recruiter/jobs`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setJobs(Array.isArray(data) ? data : data.jobs ?? []))
      .catch(() => {});
  }, []);

  // Fetch analytics data
  useEffect(() => {
    setLoading(true);

    const funnelUrl = new URL(`${API_BASE}/api/recruiter/analytics/funnel`);
    if (selectedJob) funnelUrl.searchParams.set("job_id", selectedJob);

    Promise.all([
      fetch(funnelUrl.toString(), { credentials: "include" }).then((r) =>
        r.ok ? r.json() : { funnel: [] },
      ),
      fetch(`${API_BASE}/api/recruiter/analytics/time-to-hire`, {
        credentials: "include",
      }).then((r) =>
        r.ok ? r.json() : { count: 0, avg_days: null, median_days: null, p75_days: null },
      ),
      fetch(`${API_BASE}/api/recruiter/analytics/conversions`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : { conversions: [] })),
      fetch(`${API_BASE}/api/recruiter/analytics/sources`, {
        credentials: "include",
      }).then((r) => (r.ok ? r.json() : { sources: [] })),
    ])
      .then(([funnelData, tthData, convData, srcData]) => {
        setFunnel(funnelData.funnel ?? []);
        setTth(tthData);
        setConversions(convData.conversions ?? []);
        setSources(srcData.sources ?? []);
      })
      .finally(() => setLoading(false));
  }, [selectedJob]);

  const maxFunnelCount = Math.max(...funnel.map((f) => f.count), 1);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading analytics...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
          <p className="mt-1 text-sm text-slate-500">
            Pipeline performance, conversions, and source effectiveness
          </p>
        </div>
        <select
          value={selectedJob}
          onChange={(e) => setSelectedJob(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        >
          <option value="">All Jobs</option>
          {jobs.map((j) => (
            <option key={j.id} value={j.id}>
              {j.title}
            </option>
          ))}
        </select>
      </div>

      {/* Pipeline Funnel */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Pipeline Funnel</h2>
        {funnel.every((f) => f.count === 0) ? (
          <p className="py-6 text-center text-sm text-slate-400">
            No pipeline data yet. Add candidates to your pipeline to see the funnel.
          </p>
        ) : (
          <div className="space-y-3">
            {funnel.map((f) => {
              const pct = (f.count / maxFunnelCount) * 100;
              return (
                <div key={f.stage} className="flex items-center gap-3">
                  <span className="w-24 text-right text-sm font-medium capitalize text-slate-600">
                    {f.stage}
                  </span>
                  <div className="flex-1">
                    <div className="h-8 overflow-hidden rounded-md bg-slate-50">
                      <div
                        className={`flex h-full items-center rounded-md ${STAGE_COLORS[f.stage] ?? "bg-slate-200"} transition-all`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      >
                        <span
                          className={`px-2 text-xs font-semibold ${STAGE_TEXT[f.stage] ?? "text-slate-700"}`}
                        >
                          {f.count}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Time-to-Hire */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Time to Hire</h2>
        {!tth || tth.count === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">
            Not enough data. Hire candidates through your pipeline to see metrics.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">{tth.count}</p>
              <p className="mt-1 text-xs text-slate-500">Total Hires</p>
            </div>
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">
                {tth.avg_days != null ? `${tth.avg_days}d` : "--"}
              </p>
              <p className="mt-1 text-xs text-slate-500">Average</p>
            </div>
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">
                {tth.median_days != null ? `${tth.median_days}d` : "--"}
              </p>
              <p className="mt-1 text-xs text-slate-500">Median</p>
            </div>
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-center">
              <p className="text-2xl font-bold text-slate-900">
                {tth.p75_days != null ? `${tth.p75_days}d` : "--"}
              </p>
              <p className="mt-1 text-xs text-slate-500">75th Percentile</p>
            </div>
          </div>
        )}
      </div>

      {/* Conversion Rates */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Conversion Rates</h2>
        {conversions.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">No conversion data available.</p>
        ) : (
          <div className="space-y-3">
            {conversions.map((c) => (
              <div key={`${c.from_stage}-${c.to_stage}`} className="flex items-center gap-3">
                <div className="flex w-48 items-center gap-1 text-sm">
                  <span className="capitalize text-slate-600">{c.from_stage}</span>
                  <span className="text-slate-300">&rarr;</span>
                  <span className="capitalize text-slate-600">{c.to_stage}</span>
                </div>
                <div className="flex-1">
                  <div className="h-5 overflow-hidden rounded bg-slate-50">
                    <div
                      className="h-full rounded bg-blue-200 transition-all"
                      style={{ width: `${Math.max(c.rate, 1)}%` }}
                    />
                  </div>
                </div>
                <span className="w-16 text-right text-sm font-semibold text-slate-700">
                  {c.rate}%
                </span>
                <span className="w-20 text-right text-xs text-slate-400">
                  {c.to_count}/{c.from_count}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Source Effectiveness */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Source Effectiveness</h2>
        {sources.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">
            No source data yet. Track where your candidates come from.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="pb-2 font-medium text-slate-500">Source</th>
                  <th className="pb-2 text-right font-medium text-slate-500">Total</th>
                  <th className="pb-2 text-right font-medium text-slate-500">Hired</th>
                  <th className="pb-2 text-right font-medium text-slate-500">Hire Rate</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s, i) => (
                  <tr
                    key={s.source}
                    className={`border-b border-slate-100 ${i % 2 === 1 ? "bg-slate-50/50" : ""}`}
                  >
                    <td className="py-2.5 font-medium capitalize text-slate-700">{s.source}</td>
                    <td className="py-2.5 text-right text-slate-600">{s.total}</td>
                    <td className="py-2.5 text-right text-slate-600">{s.hired}</td>
                    <td className="py-2.5 text-right font-semibold text-slate-700">
                      {s.hire_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
