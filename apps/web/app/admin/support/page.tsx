"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type Alert = {
  type: string;
  severity: string;
  message: string;
  action_url: string | null;
};

type OverviewData = {
  system_health: {
    api: { status: string };
    database: { status: string; detail?: string };
    redis: { status: string };
    queues: {
      redis_connected: boolean;
      total_pending: number;
      total_failed: number;
    };
  };
  platform_stats: {
    total_users: number;
    users_by_role: Record<string, number>;
    users_created_last_7d: number;
    users_created_last_30d: number;
  };
  billing_stats: {
    candidates_by_tier: Record<string, number>;
    employers_by_tier: Record<string, number>;
    recruiters_by_tier: Record<string, number>;
  };
  alerts: Alert[];
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`}
    />
  );
}

function TierTable({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-slate-700">{title}</h3>
      <div className="flex flex-wrap gap-2">
        {entries.map(([tier, count]) => (
          <span
            key={tier}
            className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
          >
            {tier || "none"}: {count}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function SupportOverviewPage() {
  const router = useRouter();
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/admin/support/overview`, {
          credentials: "include",
        });
        if (res.status === 401) {
          router.push("/login");
          return;
        }
        if (res.status === 403) {
          setError("Admin access required.");
          return;
        }
        if (!res.ok) throw new Error("Failed to load overview");
        setData(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load overview");
      }
    };
    void load();
  }, [router]);

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!data) {
    return <p className="text-sm text-slate-500">Loading...</p>;
  }

  const { system_health: sh, platform_stats: ps, billing_stats: bs, alerts } = data;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-semibold">Support Dashboard</h1>
        <p className="mt-1 text-sm text-slate-600">
          System health, platform stats, and actionable alerts.
        </p>
      </header>

      {/* Status cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            System Health
          </div>
          <div className="mt-3 flex flex-col gap-2 text-sm">
            <div className="flex items-center gap-2">
              <StatusDot ok={sh.api.status === "ok"} /> API
            </div>
            <div className="flex items-center gap-2">
              <StatusDot ok={sh.database.status === "ok"} /> Database
            </div>
            <div className="flex items-center gap-2">
              <StatusDot ok={sh.redis.status === "ok"} /> Redis
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Queues
          </div>
          <div className="mt-3 text-2xl font-bold text-slate-900">
            {sh.queues.total_pending}{" "}
            <span className="text-sm font-normal text-slate-500">pending</span>
          </div>
          {sh.queues.total_failed > 0 && (
            <div className="mt-1 text-sm font-semibold text-red-600">
              {sh.queues.total_failed} failed
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Users
          </div>
          <div className="mt-3 text-2xl font-bold text-slate-900">
            {ps.total_users}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            +{ps.users_created_last_7d} this week / +{ps.users_created_last_30d}{" "}
            this month
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Alerts
          </div>
          <div className="mt-3 text-2xl font-bold text-slate-900">
            {alerts.length}
          </div>
          {alerts.length > 0 && (
            <div className="mt-1 text-xs text-amber-600">
              {alerts.filter((a) => a.severity === "error").length} errors,{" "}
              {alerts.filter((a) => a.severity === "warning").length} warnings
            </div>
          )}
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Alerts</h2>
          <div className="flex flex-col gap-2">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm ${
                  alert.severity === "error"
                    ? "bg-red-50 text-red-800"
                    : "bg-amber-50 text-amber-800"
                }`}
              >
                <span>{alert.message}</span>
                {alert.action_url && (
                  <Link
                    href={alert.action_url}
                    className="text-xs font-semibold underline"
                  >
                    View
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Billing distribution */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">
          Billing Distribution
        </h2>
        <div className="flex flex-col gap-4">
          <TierTable title="Candidates" data={bs.candidates_by_tier} />
          <TierTable title="Employers" data={bs.employers_by_tier} />
          <TierTable title="Recruiters" data={bs.recruiters_by_tier} />
        </div>
      </div>

      {/* Users by role */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">
          Users by Role
        </h2>
        <div className="flex flex-wrap gap-2">
          {Object.entries(ps.users_by_role).map(([role, count]) => (
            <span
              key={role}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
            >
              {role}: {count}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
