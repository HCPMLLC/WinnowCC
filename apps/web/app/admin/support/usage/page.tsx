"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type UsageData = {
  period: string;
  total_match_refreshes: number;
  total_tailor_requests: number;
  daily_usage_summary: Record<string, { total: number; unique_users: number }>;
  top_users: { user_id: number; email: string; total_usage: number }[];
  sieve_stats: {
    total_conversations: number;
    total_messages: number;
    active_users_7d: number;
  };
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function FeatureUsagePage() {
  const router = useRouter();
  const [data, setData] = useState<UsageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/admin/support/feature-usage`, {
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
        if (!res.ok) throw new Error("Failed to load usage data");
        setData(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
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

  const dailyEntries = Object.entries(data.daily_usage_summary);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-semibold">Feature Usage</h1>
        <p className="mt-1 text-sm text-slate-600">
          Period: {data.period}
        </p>
      </header>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Match Refreshes
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {data.total_match_refreshes}
          </div>
          <div className="text-xs text-slate-500">this month</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Tailor Requests
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {data.total_tailor_requests}
          </div>
          <div className="text-xs text-slate-500">this month</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Sieve Conversations
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {data.sieve_stats.total_conversations}
          </div>
          <div className="text-xs text-slate-500">
            {data.sieve_stats.total_messages} messages total
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Active Sieve Users
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {data.sieve_stats.active_users_7d}
          </div>
          <div className="text-xs text-slate-500">last 7 days</div>
        </div>
      </div>

      {/* Daily usage breakdown */}
      {dailyEntries.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            Daily Usage Breakdown (Today)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2 pr-3">Counter</th>
                  <th className="pb-2 pr-3">Total Today</th>
                  <th className="pb-2">Unique Users</th>
                </tr>
              </thead>
              <tbody>
                {dailyEntries.map(([name, info]) => (
                  <tr key={name} className="border-b border-slate-100">
                    <td className="py-2 pr-3 font-medium text-slate-700">
                      {name}
                    </td>
                    <td className="py-2 pr-3">{info.total}</td>
                    <td className="py-2">{info.unique_users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Top users */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">
          Top 10 Users by Monthly Usage
        </h2>
        {data.top_users.length === 0 ? (
          <p className="text-xs text-slate-400">No usage data yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2 pr-3">#</th>
                  <th className="pb-2 pr-3">Email</th>
                  <th className="pb-2">Total Usage</th>
                </tr>
              </thead>
              <tbody>
                {data.top_users.map((u, i) => (
                  <tr key={u.user_id} className="border-b border-slate-100">
                    <td className="py-2 pr-3 text-slate-400">{i + 1}</td>
                    <td className="py-2 pr-3">
                      <Link
                        href={`/admin/support/lookup?q=${encodeURIComponent(u.email)}`}
                        className="text-blue-600 hover:underline"
                      >
                        {u.email}
                      </Link>
                    </td>
                    <td className="py-2 font-semibold">{u.total_usage}</td>
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
