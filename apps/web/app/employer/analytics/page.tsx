"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Overview {
  active_jobs: number;
  total_impressions: number;
  total_clicks: number;
  total_applications: number;
  total_cost: number;
}

interface CostMetrics {
  total_cost: number;
  total_clicks: number;
  total_applications: number;
  cost_per_click: number;
  cost_per_application: number;
}

interface Recommendation {
  board_connection_id: string;
  total_applications: number;
  total_clicks: number;
  cost_per_application: number;
  recommendation: string;
}

export default function EmployerAnalyticsPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [cost, setCost] = useState<CostMetrics | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [overviewRes, costRes, recsRes] = await Promise.all([
          fetch(`${API_BASE}/api/employer/analytics/overview`, {
            credentials: "include",
          }),
          fetch(`${API_BASE}/api/employer/analytics/cost`, {
            credentials: "include",
          }),
          fetch(`${API_BASE}/api/employer/analytics/recommendations`, {
            credentials: "include",
          }),
        ]);

        if (overviewRes.ok) setOverview(await overviewRes.json());
        if (costRes.ok) setCost(await costRes.json());
        if (recsRes.ok) setRecommendations(await recsRes.json());
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load analytics",
        );
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
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
        <h1 className="text-3xl font-bold text-slate-900">
          Cross-Board Analytics
        </h1>
        <p className="mt-1 text-slate-600">
          Performance metrics across all your job boards
        </p>
      </div>

      {/* Summary Cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Active Jobs"
          value={overview?.active_jobs ?? 0}
          color="border-l-blue-500"
        />
        <MetricCard
          title="Total Impressions"
          value={(overview?.total_impressions ?? 0).toLocaleString()}
          color="border-l-emerald-500"
        />
        <MetricCard
          title="Total Clicks"
          value={(overview?.total_clicks ?? 0).toLocaleString()}
          color="border-l-amber-500"
        />
        <MetricCard
          title="Applications"
          value={(overview?.total_applications ?? 0).toLocaleString()}
          color="border-l-purple-500"
        />
      </div>

      {/* Cost Metrics */}
      {cost && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Cost-Per-Outcome
          </h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <div>
              <p className="text-sm text-slate-500">Total Spend</p>
              <p className="text-2xl font-bold text-slate-900">
                ${cost.total_cost.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Cost per Click</p>
              <p className="text-2xl font-bold text-slate-900">
                ${cost.cost_per_click.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Cost per Application</p>
              <p className="text-2xl font-bold text-slate-900">
                ${cost.cost_per_application.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Board Recommendations */}
      {recommendations.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Board Recommendations
          </h2>
          <div className="space-y-3">
            {recommendations.map((rec) => (
              <div
                key={rec.board_connection_id}
                className="flex items-center justify-between rounded-lg border border-slate-100 p-4"
              >
                <div>
                  <p className="font-medium text-slate-900">
                    Board {rec.board_connection_id.slice(0, 8)}
                  </p>
                  <p className="text-sm text-slate-500">
                    {rec.total_applications} applications &middot; $
                    {rec.cost_per_application.toFixed(2)} CPA
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    rec.recommendation === "high_performer"
                      ? "bg-emerald-100 text-emerald-800"
                      : rec.recommendation === "moderate"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {rec.recommendation.replace("_", " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  title,
  value,
  color,
}: {
  title: string;
  value: string | number;
  color: string;
}) {
  return (
    <div
      className={`rounded-xl border border-slate-200 border-l-4 bg-white p-5 shadow-sm ${color}`}
    >
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}
