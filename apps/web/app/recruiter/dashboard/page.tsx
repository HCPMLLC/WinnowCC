"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface RecruiterProfile {
  company_name: string;
  subscription_tier: string;
  is_trial_active: boolean;
  trial_days_remaining: number;
}

interface PipelineStageSummary {
  stage: string;
  count: number;
}

interface Activity {
  id: number;
  activity_type: string;
  subject: string | null;
  created_at: string;
}

interface DashboardStats {
  total_active_jobs: number;
  total_pipeline_candidates: number;
  total_clients: number;
  total_placements: number;
  pipeline_by_stage: PipelineStageSummary[];
  recent_activities: Activity[];
  subscription_tier: string;
}

const STAGE_COLORS: Record<string, string> = {
  sourced: "bg-slate-200",
  contacted: "bg-blue-200",
  screening: "bg-amber-200",
  interviewing: "bg-purple-200",
  offered: "bg-emerald-200",
  placed: "bg-green-300",
  rejected: "bg-red-200",
};

export default function RecruiterDashboard() {
  const [profile, setProfile] = useState<RecruiterProfile | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/recruiter/profile`, { credentials: "include" }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE}/api/recruiter/dashboard`, { credentials: "include" }).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([p, s]) => {
        setProfile(p);
        setStats(s);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center py-20"><div className="text-sm text-slate-500">Loading dashboard...</div></div>;
  }

  return (
    <div className="space-y-6">
      {/* Trial banner */}
      {profile?.is_trial_active && (
        <div className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="font-semibold text-amber-900">Free trial: {profile.trial_days_remaining} day{profile.trial_days_remaining !== 1 ? "s" : ""} remaining</p>
            <p className="mt-0.5 text-sm text-amber-700">Upgrade to keep full access after your trial ends.</p>
          </div>
          <Link href="/recruiter/pricing" className="self-start rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-900 transition-colors hover:bg-amber-400 sm:self-auto">View Plans</Link>
        </div>
      )}

      {/* Welcome card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Welcome{profile?.company_name ? `, ${profile.company_name}` : ""}</h1>
        <p className="mt-1 text-slate-600">Source candidates, manage your pipeline, and close placements faster.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/recruiter/candidates" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800">Source Candidates</Link>
          <Link href="/recruiter/pipeline" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50">View Pipeline</Link>
          <Link href="/recruiter/clients" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50">Manage Clients</Link>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Active Jobs</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{stats?.total_active_jobs ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Pipeline</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{stats?.total_pipeline_candidates ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Clients</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{stats?.total_clients ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Placements</p>
          <p className="mt-2 text-3xl font-bold text-emerald-600">{stats?.total_placements ?? 0}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Pipeline by stage */}
        {stats?.pipeline_by_stage && stats.pipeline_by_stage.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-slate-900">Pipeline by Stage</h2>
            <div className="space-y-3">
              {stats.pipeline_by_stage.map((s) => {
                const maxCount = Math.max(1, ...stats.pipeline_by_stage.map((x) => x.count));
                return (
                  <div key={s.stage} className="flex items-center gap-3">
                    <span className="w-24 text-sm capitalize text-slate-600">{s.stage}</span>
                    <div className="flex-1">
                      <div className={`h-6 rounded ${STAGE_COLORS[s.stage] || "bg-slate-200"}`} style={{ width: `${Math.min(100, (s.count / maxCount) * 100)}%`, minWidth: "2rem" }}>
                        <span className="px-2 text-xs font-medium leading-6 text-slate-700">{s.count}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Recent activities */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Recent Activity</h2>
          {!stats?.recent_activities || stats.recent_activities.length === 0 ? (
            <p className="text-sm text-slate-500">No recent activity.</p>
          ) : (
            <div className="space-y-3">
              {stats.recent_activities.slice(0, 8).map((a) => (
                <div key={a.id} className="flex items-start gap-3 border-l-2 border-slate-200 pl-3">
                  <div>
                    <p className="text-sm font-medium text-slate-700">{a.subject || a.activity_type}</p>
                    <p className="text-xs text-slate-400">{new Date(a.created_at).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Plan info */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Current Plan</p>
            <p className="mt-1 text-xl font-bold capitalize text-slate-900">{stats?.subscription_tier ?? profile?.subscription_tier ?? "trial"}</p>
          </div>
          <Link href="/recruiter/settings" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Manage Plan</Link>
        </div>
      </div>
    </div>
  );
}
