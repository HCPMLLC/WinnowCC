"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

type MonthlyDataPoint = {
  month: string;
  new_signups: number;
  new_paid: number;
};

type TrendData = {
  points: MonthlyDataPoint[];
};

type OverallKpis = {
  total_users: number;
  users_by_role: Record<string, number>;
  new_users_7d: number;
  new_users_30d: number;
};

type CandidateKpis = {
  total: number;
  by_tier: Record<string, number>;
  resume_upload_rate: number;
  avg_matches_per_candidate: number;
  avg_match_score: number;
  application_funnel: Record<string, number>;
  tailored_resumes_total: number;
  sieve_adoption_rate: number;
  onboarding_completion_rate: number;
};

type EmployerKpis = {
  total: number;
  by_tier: Record<string, number>;
  active_jobs: number;
  avg_jobs_per_employer: number;
  avg_views_per_job: number;
  avg_applications_per_job: number;
  onboarding_completion_rate: number;
};

type RecruiterKpis = {
  total: number;
  by_tier: Record<string, number>;
  total_pipeline_candidates: number;
  avg_pipeline_per_recruiter: number;
  pipeline_stage_distribution: Record<string, number>;
  avg_seat_utilization: number;
  total_jobs_posted: number;
  onboarding_completion_rate: number;
};

type KpiData = {
  overall: OverallKpis;
  candidates: CandidateKpis;
  employers: EmployerKpis;
  recruiters: RecruiterKpis;
  trends: Record<string, TrendData>;
  generated_at: string;
};

// ─── Helper components ────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function TierBadges({ data }: { data: Record<string, number> }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(data).map(([tier, count]) => (
        <span
          key={tier}
          className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
        >
          {tier}: {count}
        </span>
      ))}
    </div>
  );
}

function RateBar({ label, rate }: { label: string; rate: number }) {
  const pct = Math.round(rate * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-800">{pct}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100">
        <div
          className="h-2 rounded-full bg-indigo-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function FunnelRow({ data }: { data: Record<string, number> }) {
  const order = ["saved", "applied", "interviewing", "offer", "rejected"];
  const entries = order
    .filter((k) => k in data)
    .map((k) => [k, data[k]] as [string, number]);
  if (!entries.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {entries.map(([stage, count], i) => (
        <span key={stage} className="flex items-center gap-2">
          {i > 0 && <span className="text-slate-300">→</span>}
          <span className="font-medium text-slate-800">{count}</span>
          <span className="text-slate-500">{stage}</span>
        </span>
      ))}
    </div>
  );
}

// Pure-CSS vertical bar chart (no external library)
function BarChart({ points }: { points: MonthlyDataPoint[] }) {
  const max =
    Math.max(...points.flatMap((p) => [p.new_signups, p.new_paid]), 1);
  return (
    <div>
      <div className="flex items-end gap-0.5 h-28">
        {points.map((pt, i) => (
          <div
            key={i}
            className="flex flex-1 flex-col-reverse items-center gap-0.5"
          >
            <div
              title={`New signups: ${pt.new_signups}`}
              className="w-full rounded-t bg-indigo-400 min-h-[2px]"
              style={{ height: `${(pt.new_signups / max) * 100}%` }}
            />
            <div
              title={`New paid: ${pt.new_paid}`}
              className="w-full rounded-t bg-emerald-400 min-h-[2px]"
              style={{ height: `${(pt.new_paid / max) * 100}%` }}
            />
          </div>
        ))}
      </div>
      {/* Month labels */}
      <div className="flex gap-0.5 mt-1">
        {points.map((pt, i) => (
          <div
            key={i}
            className="flex-1 text-center text-[9px] text-slate-400 truncate"
          >
            {pt.month.slice(5)}
          </div>
        ))}
      </div>
      {/* Legend */}
      <div className="flex gap-4 mt-2">
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <span className="inline-block w-3 h-3 rounded-sm bg-indigo-400" />
          New signups
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <span className="inline-block w-3 h-3 rounded-sm bg-emerald-400" />
          New paid
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="mb-4 text-base font-semibold text-slate-900">{title}</h2>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function KpiDashboardPage() {
  const [data, setData] = useState<KpiData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/admin/support/kpi-dashboard`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-slate-500">Loading KPI data…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load KPI data: {error}
      </div>
    );
  }

  const { overall, candidates, employers, recruiters, trends } = data;
  const generatedAt = new Date(data.generated_at).toLocaleString();

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Platform KPIs</h1>
        <p className="text-xs text-slate-400">Generated {generatedAt}</p>
      </div>

      {/* ── Overall ──────────────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <SectionHeader title="Overall" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total Users" value={overall.total_users} />
          <StatCard label="New (7 d)" value={overall.new_users_7d} />
          <StatCard label="New (30 d)" value={overall.new_users_30d} />
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
              By Segment
            </p>
            <div className="mt-2 space-y-1 text-sm">
              {Object.entries(overall.users_by_role).map(([role, n]) => (
                <div key={role} className="flex justify-between">
                  <span className="capitalize text-slate-600">{role}</span>
                  <span className="font-semibold text-slate-800">{n}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        {/* Total trend */}
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            All Segments — Monthly Trend (12 mo)
          </p>
          <BarChart points={trends.total?.points ?? []} />
        </div>
      </section>

      {/* ── Candidates ───────────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <SectionHeader title={`Candidates (${candidates.total.toLocaleString()})`} />

        {/* Tier */}
        <div className="mb-4">
          <p className="mb-1.5 text-xs text-slate-500">Plan Tiers</p>
          <TierBadges data={candidates.by_tier} />
        </div>

        {/* Stat grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <StatCard
            label="Avg Matches"
            value={candidates.avg_matches_per_candidate.toFixed(1)}
            sub="per candidate"
          />
          <StatCard
            label="Avg Match Score"
            value={candidates.avg_match_score.toFixed(1)}
            sub="out of 100"
          />
          <StatCard
            label="Tailored Resumes"
            value={candidates.tailored_resumes_total.toLocaleString()}
            sub="total generated"
          />
          <StatCard
            label="Sieve Users"
            value={`${Math.round(candidates.sieve_adoption_rate * 100)}%`}
            sub="AI concierge adoption"
          />
        </div>

        {/* Rate bars */}
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <RateBar label="Resume Upload Rate" rate={candidates.resume_upload_rate} />
          <RateBar
            label="Onboarding Complete"
            rate={candidates.onboarding_completion_rate}
          />
          <RateBar label="Sieve Adoption" rate={candidates.sieve_adoption_rate} />
        </div>

        {/* Application funnel */}
        {Object.keys(candidates.application_funnel).length > 0 && (
          <div className="mt-4">
            <p className="mb-1.5 text-xs text-slate-500">Application Funnel</p>
            <FunnelRow data={candidates.application_funnel} />
          </div>
        )}

        {/* Trend chart */}
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Monthly Trend — Candidates (12 mo)
          </p>
          <BarChart points={trends.candidates?.points ?? []} />
        </div>
      </section>

      {/* ── Employers ────────────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <SectionHeader title={`Employers (${employers.total.toLocaleString()})`} />

        <div className="mb-4">
          <p className="mb-1.5 text-xs text-slate-500">Plan Tiers</p>
          <TierBadges data={employers.by_tier} />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <StatCard
            label="Active Jobs"
            value={employers.active_jobs.toLocaleString()}
          />
          <StatCard
            label="Avg Jobs / Employer"
            value={employers.avg_jobs_per_employer.toFixed(1)}
          />
          <StatCard
            label="Avg Views / Job"
            value={employers.avg_views_per_job.toFixed(1)}
          />
          <StatCard
            label="Avg Apps / Job"
            value={employers.avg_applications_per_job.toFixed(1)}
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <RateBar
            label="Onboarding Complete"
            rate={employers.onboarding_completion_rate}
          />
        </div>

        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Monthly Trend — Employers (12 mo)
          </p>
          <BarChart points={trends.employers?.points ?? []} />
        </div>
      </section>

      {/* ── Recruiters ───────────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <SectionHeader title={`Recruiters (${recruiters.total.toLocaleString()})`} />

        <div className="mb-4">
          <p className="mb-1.5 text-xs text-slate-500">Plan Tiers</p>
          <TierBadges data={recruiters.by_tier} />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <StatCard
            label="Pipeline Candidates"
            value={recruiters.total_pipeline_candidates.toLocaleString()}
            sub="total across CRMs"
          />
          <StatCard
            label="Avg Pipeline Size"
            value={recruiters.avg_pipeline_per_recruiter.toFixed(1)}
            sub="per recruiter"
          />
          <StatCard
            label="Jobs Posted"
            value={recruiters.total_jobs_posted.toLocaleString()}
            sub="non-draft"
          />
          <StatCard
            label="Seat Utilization"
            value={`${Math.round(recruiters.avg_seat_utilization * 100)}%`}
            sub="team & agency tiers"
          />
        </div>

        {/* Pipeline stage distribution */}
        {Object.keys(recruiters.pipeline_stage_distribution).length > 0 && (
          <div className="mt-4">
            <p className="mb-1.5 text-xs text-slate-500">
              Pipeline Stage Distribution
            </p>
            <FunnelRow data={recruiters.pipeline_stage_distribution} />
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <RateBar
            label="Onboarding Complete"
            rate={recruiters.onboarding_completion_rate}
          />
          <RateBar
            label="Seat Utilization (team/agency)"
            rate={recruiters.avg_seat_utilization}
          />
        </div>

        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Monthly Trend — Recruiters (12 mo)
          </p>
          <BarChart points={trends.recruiters?.points ?? []} />
        </div>
      </section>
    </div>
  );
}
