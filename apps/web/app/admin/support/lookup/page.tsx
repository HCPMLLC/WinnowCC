"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { parseApiError } from "../../../lib/api-error";

type CandidateInfo = {
  plan_tier: string | null;
  subscription_status: string | null;
  match_count: number;
  trust_status: string | null;
};

type EmployerInfo = {
  company_name: string;
  subscription_tier: string;
  subscription_status: string | null;
  active_jobs: number;
};

type RecruiterInfo = {
  company_name: string;
  subscription_tier: string;
  subscription_status: string | null;
  seats_purchased: number;
  seats_used: number;
};

type UsageInfo = {
  monthly_match_refreshes: number;
  monthly_tailor_requests: number;
  daily_counters: Record<string, number>;
};

type ActivityEntry = {
  type: string;
  detail: string;
  status: string | null;
  created_at: string;
};

type UserResult = {
  user: {
    id: number;
    email: string;
    role: string;
    is_admin: boolean;
    created_at: string;
    onboarding_completed: boolean;
    mfa_required: boolean;
  };
  candidate: CandidateInfo | null;
  employer: EmployerInfo | null;
  recruiter: RecruiterInfo | null;
  usage: UsageInfo;
  recent_activity: ActivityEntry[];
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function Badge({ text, color }: { text: string; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-100 text-blue-800",
    green: "bg-emerald-100 text-emerald-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
    slate: "bg-slate-100 text-slate-800",
    purple: "bg-purple-100 text-purple-800",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${colors[color] ?? colors.slate}`}
    >
      {text}
    </span>
  );
}

function UserCard({ result }: { result: UserResult }) {
  const router = useRouter();
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [tierInput, setTierInput] = useState("");
  const [segInput, setSegInput] = useState("candidate");

  const doAction = async (path: string, opts?: RequestInit) => {
    setActionMsg(null);
    setActionErr(null);
    try {
      const res = await fetch(`${API}/api/admin/support/actions/${path}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        ...opts,
      });
      if (res.status === 401) {
        router.push("/login");
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        setActionErr(parseApiError(data, "Action failed"));
        return;
      }
      setActionMsg(data.message);
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : "Action failed");
    }
  };

  const { user, candidate, employer, recruiter, usage, recent_activity } =
    result;

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-lg font-semibold text-slate-900">
          {user.email}
        </span>
        <Badge text={user.role} color="blue" />
        {user.is_admin && <Badge text="admin" color="purple" />}
        <span className="text-xs text-slate-400">ID: {user.id}</span>
        <span className="text-xs text-slate-400">
          Joined {new Date(user.created_at).toLocaleDateString()}
        </span>
        {user.onboarding_completed && (
          <Badge text="onboarded" color="green" />
        )}
        {user.mfa_required && <Badge text="MFA" color="amber" />}
      </div>

      {/* Segment details */}
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {candidate && (
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase text-slate-400">
              Candidate
            </div>
            <div className="mt-2 flex flex-col gap-1 text-sm">
              <div>
                Tier:{" "}
                <span className="font-medium">
                  {candidate.plan_tier ?? "free"}
                </span>
              </div>
              <div>
                Status:{" "}
                <span className="font-medium">
                  {candidate.subscription_status ?? "none"}
                </span>
              </div>
              <div>Matches: {candidate.match_count}</div>
              {candidate.trust_status && (
                <div>
                  Trust:{" "}
                  <Badge
                    text={candidate.trust_status}
                    color={
                      candidate.trust_status === "allowed" ? "green" : "red"
                    }
                  />
                </div>
              )}
            </div>
          </div>
        )}
        {employer && (
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase text-slate-400">
              Employer
            </div>
            <div className="mt-2 flex flex-col gap-1 text-sm">
              <div className="font-medium">{employer.company_name}</div>
              <div>
                Tier:{" "}
                <span className="font-medium">
                  {employer.subscription_tier}
                </span>
              </div>
              <div>
                Status:{" "}
                <span className="font-medium">
                  {employer.subscription_status ?? "none"}
                </span>
              </div>
              <div>Active Jobs: {employer.active_jobs}</div>
            </div>
          </div>
        )}
        {recruiter && (
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase text-slate-400">
              Recruiter
            </div>
            <div className="mt-2 flex flex-col gap-1 text-sm">
              <div className="font-medium">{recruiter.company_name}</div>
              <div>
                Tier:{" "}
                <span className="font-medium">
                  {recruiter.subscription_tier}
                </span>
              </div>
              <div>
                Seats: {recruiter.seats_used}/{recruiter.seats_purchased}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Usage */}
      <div className="mt-4 rounded-2xl bg-slate-50 p-4">
        <div className="text-xs font-semibold uppercase text-slate-400">
          Usage
        </div>
        <div className="mt-2 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="text-xs text-slate-500">Monthly Match Refreshes</div>
            <div className="text-lg font-semibold">
              {usage.monthly_match_refreshes}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Monthly Tailor Requests</div>
            <div className="text-lg font-semibold">
              {usage.monthly_tailor_requests}
            </div>
          </div>
          {Object.entries(usage.daily_counters).map(([name, count]) => (
            <div key={name}>
              <div className="text-xs text-slate-500">{name} (today)</div>
              <div className="text-lg font-semibold">{count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent activity */}
      {recent_activity.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase text-slate-400">
            Recent Activity
          </div>
          <div className="mt-2 max-h-48 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-1 pr-3">Type</th>
                  <th className="pb-1 pr-3">Detail</th>
                  <th className="pb-1 pr-3">Status</th>
                  <th className="pb-1">Time</th>
                </tr>
              </thead>
              <tbody>
                {recent_activity.map((a, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-1 pr-3">
                      <Badge
                        text={a.type}
                        color={a.type === "job_run" ? "blue" : "amber"}
                      />
                    </td>
                    <td className="py-1 pr-3 text-slate-700">{a.detail}</td>
                    <td className="py-1 pr-3">
                      {a.status && (
                        <Badge
                          text={a.status}
                          color={
                            a.status === "completed" || a.status === "allowed"
                              ? "green"
                              : a.status === "failed"
                                ? "red"
                                : "slate"
                          }
                        />
                      )}
                    </td>
                    <td className="py-1 text-slate-500">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="mt-4 border-t border-slate-100 pt-4">
        <div className="text-xs font-semibold uppercase text-slate-400">
          Quick Actions
        </div>

        {actionMsg && (
          <div className="mt-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
            {actionMsg}
          </div>
        )}
        {actionErr && (
          <div className="mt-2 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700">
            {actionErr}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-end gap-3">
          {/* Tier override */}
          <div className="flex items-end gap-2">
            <div>
              <label className="block text-xs text-slate-500">Segment</label>
              <select
                value={segInput}
                onChange={(e) => setSegInput(e.target.value)}
                className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
              >
                <option value="candidate">Candidate</option>
                <option value="employer">Employer</option>
                <option value="recruiter">Recruiter</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500">Tier</label>
              <input
                value={tierInput}
                onChange={(e) => setTierInput(e.target.value)}
                placeholder="e.g. pro"
                className="w-24 rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
              />
            </div>
            <button
              onClick={() =>
                doAction("tier-override", {
                  body: JSON.stringify({
                    user_id: user.id,
                    segment: segInput,
                    tier: tierInput,
                  }),
                })
              }
              disabled={!tierInput}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            >
              Override Tier
            </button>
          </div>

          <button
            onClick={() => doAction(`reparse/${user.id}`)}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white"
          >
            Re-parse Resume
          </button>

          <button
            onClick={() => doAction(`clear-daily-counters/${user.id}`)}
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white"
          >
            Clear Daily Counters
          </button>

          <button
            onClick={() => doAction(`reset-monthly-usage/${user.id}`)}
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white"
          >
            Reset Monthly Usage
          </button>
        </div>
      </div>
    </div>
  );
}

export default function UserLookupPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(initialQ);
  const [results, setResults] = useState<UserResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  const search = useCallback(
    async (q?: string) => {
      const term = (q ?? query).trim();
      if (!term) return;
      setSearching(true);
      setError(null);
      try {
        const res = await fetch(
          `${API}/api/admin/support/user-lookup?q=${encodeURIComponent(term)}`,
          { credentials: "include" },
        );
        if (res.status === 401) {
          router.push("/login");
          return;
        }
        if (res.status === 403) {
          setError("Admin access required.");
          return;
        }
        if (!res.ok) throw new Error("Search failed");
        setResults(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed");
      } finally {
        setSearching(false);
      }
    },
    [query, router],
  );

  useEffect(() => {
    if (initialQ) {
      void search(initialQ);
    }
  }, [initialQ, search]);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-semibold">User Lookup</h1>
        <p className="mt-1 text-sm text-slate-600">
          Search by email or user ID to view the complete user picture.
        </p>
      </header>

      <div className="flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search by email or user ID..."
          className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-sm focus:border-slate-400 focus:outline-none"
        />
        <button
          onClick={search}
          disabled={searching || !query.trim()}
          className="rounded-xl bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {searching ? "Searching..." : "Search"}
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {results.length === 0 && !error && !searching && query && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          No users found.
        </div>
      )}

      <div className="flex flex-col gap-4">
        {results.map((r) => (
          <UserCard key={r.user.id} result={r} />
        ))}
      </div>
    </div>
  );
}
