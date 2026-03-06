"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Analytics {
  active_jobs: number;
  total_job_views: number;
  total_applications: number;
  candidate_views_this_month: number;
  candidate_views_limit: number | null;
  saved_candidates: number;
  subscription_tier: string;
  subscription_status: string;
}

export default function EmployerDashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchAnalytics() {
      try {
        const res = await fetch(`${API_BASE}/api/employer/analytics/summary`, {
          credentials: "include",
        });
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || "Failed to load analytics");
        }
        setAnalytics(await res.json());
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch analytics",
        );
      } finally {
        setIsLoading(false);
      }
    }
    fetchAnalytics();
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
          <div className="mt-2 h-4 w-64 animate-pulse rounded bg-slate-100" />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-slate-600">
          Overview of your hiring activity
        </p>
      </div>

      {/* Stats Grid */}
      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          title="Active Jobs"
          value={analytics?.active_jobs ?? 0}
          color="border-l-blue-500"
          link="/employer/jobs"
        />
        <StatCard
          title="Total Views"
          value={analytics?.total_job_views ?? 0}
          color="border-l-emerald-500"
        />
        <StatCard
          title="Applications"
          value={analytics?.total_applications ?? 0}
          color="border-l-amber-500"
        />
        <StatCard
          title="Saved Candidates"
          value={analytics?.saved_candidates ?? 0}
          color="border-l-purple-500"
          link="/employer/candidates/saved"
        />
      </div>

      {/* Candidate Views Limit */}
      {analytics?.candidate_views_limit != null && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium text-slate-900">
                Candidate Views This Month
              </h3>
              <p className="text-sm text-slate-500">
                {analytics.candidate_views_this_month} /{" "}
                {analytics.candidate_views_limit} views used
              </p>
            </div>
            {analytics.candidate_views_this_month >=
              analytics.candidate_views_limit && (
              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                Limit reached
              </span>
            )}
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full transition-all ${
                analytics.candidate_views_this_month >=
                analytics.candidate_views_limit
                  ? "bg-amber-500"
                  : "bg-blue-500"
              }`}
              style={{
                width: `${Math.min(
                  (analytics.candidate_views_this_month /
                    analytics.candidate_views_limit) *
                    100,
                  100,
                )}%`,
              }}
            />
          </div>
          {analytics.candidate_views_this_month >=
            analytics.candidate_views_limit && (
            <p className="mt-2 text-sm text-slate-500">
              You&apos;ve reached your monthly limit.{" "}
              <Link
                href="/employer/settings"
                className="font-medium text-blue-600 hover:text-blue-700"
              >
                Upgrade
              </Link>{" "}
              to view more candidates.
            </p>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">
            Post a New Job
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Create a job posting to attract candidates
          </p>
          <Link
            href="/employer/jobs/new"
            className="mt-4 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Create Job
          </Link>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">
            Search Candidates
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Find talent that matches your requirements
          </p>
          <Link
            href="/employer/candidates"
            className="mt-4 inline-block rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Search Now
          </Link>
        </div>
      </div>

      {/* Subscription Info */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-slate-900">Current Plan</h3>
            <p className="text-sm capitalize text-slate-600">
              {analytics?.subscription_tier} tier
              {analytics?.subscription_status !== "active" && (
                <span className="ml-2 text-red-600">
                  ({analytics?.subscription_status})
                </span>
              )}
            </p>
          </div>
          <Link
            href="/employer/settings"
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Manage Subscription &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  color,
  link,
}: {
  title: string;
  value: number;
  color: string;
  link?: string;
}) {
  const content = (
    <div
      className={`rounded-xl border border-slate-200 border-l-4 ${color} bg-white p-5 shadow-sm transition-shadow hover:shadow-md`}
    >
      <p className="text-sm font-medium text-slate-500">{title}</p>
      <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
    </div>
  );

  if (link) {
    return <Link href={link}>{content}</Link>;
  }
  return content;
}
