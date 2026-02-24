"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type ScheduledTask = {
  name: string;
  cron: string;
  description: string;
};

type SchedulerStatus = {
  enabled: boolean;
  ingest_cron: string;
  default_search: string;
  default_location: string;
  job_sources: string[];
  scheduled_tasks: ScheduledTask[];
};

type SchedulerRun = {
  id: number;
  job_type: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function statusColor(status: string) {
  switch (status) {
    case "completed":
      return "bg-emerald-100 text-emerald-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "running":
      return "bg-blue-100 text-blue-800";
    default:
      return "bg-slate-100 text-slate-800";
  }
}

function formatDuration(created: string, updated: string): string {
  const ms =
    new Date(updated).getTime() - new Date(created).getTime();
  if (ms < 0) return "-";
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  return `${mins}m ${rem}s`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function SchedulerControlPage() {
  const router = useRouter();
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [runs, setRuns] = useState<SchedulerRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  const load = useCallback(async () => {
    try {
      const [statusRes, runsRes] = await Promise.all([
        fetch(`${API}/api/admin/scheduler/status`, {
          credentials: "include",
        }),
        fetch(`${API}/api/admin/scheduler/runs?limit=20`, {
          credentials: "include",
        }),
      ]);
      if (statusRes.status === 401 || runsRes.status === 401) {
        router.push("/login");
        return;
      }
      if (statusRes.status === 403 || runsRes.status === 403) {
        setError("Admin access required.");
        return;
      }
      if (!statusRes.ok) throw new Error("Failed to load scheduler status");
      if (!runsRes.ok) throw new Error("Failed to load scheduler runs");
      setStatus(await statusRes.json());
      setRuns(await runsRes.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleTrigger = async () => {
    setActionMsg(null);
    setTriggering(true);
    try {
      const res = await fetch(`${API}/api/admin/scheduler/trigger`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Trigger failed");
      const result = await res.json();
      setActionMsg(`${result.message} (job_id: ${result.job_id})`);
      void load();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Trigger failed");
    } finally {
      setTriggering(false);
    }
  };

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!status) {
    return <p className="text-sm text-slate-500">Loading...</p>;
  }

  // Derive KPI values from runs
  const lastRun = runs.length > 0 ? runs[0] : null;
  const totalRuns = runs.length;
  const completedRuns = runs.filter((r) => r.status === "completed").length;
  const successRate =
    totalRuns > 0 ? Math.round((completedRuns / totalRuns) * 100) : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Scheduler Control</h1>
          <p className="mt-1 text-sm text-slate-600">
            <span
              className={`inline-block h-2 w-2 rounded-full ${status.enabled ? "bg-emerald-500" : "bg-red-500"}`}
            />{" "}
            Scheduler{" "}
            <span
              className={`font-semibold ${status.enabled ? "text-emerald-600" : "text-red-600"}`}
            >
              {status.enabled ? "enabled" : "disabled"}
            </span>
            {" \u00B7 "}
            <span className="text-slate-500">
              Cron: <code className="text-xs">{status.ingest_cron}</code>
            </span>
            {status.default_search && (
              <>
                {" \u00B7 "}
                <span className="text-slate-500">
                  Search: {status.default_search}
                </span>
              </>
            )}
            {status.default_location && (
              <>
                {" \u00B7 "}
                <span className="text-slate-500">
                  Location: {status.default_location}
                </span>
              </>
            )}
          </p>
        </div>
        <button
          onClick={() => load()}
          className="rounded-lg bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200"
        >
          Refresh
        </button>
      </header>

      {/* Action message */}
      {actionMsg && (
        <div className="rounded-xl bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {actionMsg}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <span className="text-xs text-slate-500">Last Run</span>
          {lastRun ? (
            <>
              <div className="mt-1 text-sm font-semibold text-slate-900">
                {formatTime(lastRun.created_at)}
              </div>
              <span
                className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusColor(lastRun.status)}`}
              >
                {lastRun.status}
              </span>
            </>
          ) : (
            <div className="mt-1 text-sm text-slate-400">No runs yet</div>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <span className="text-xs text-slate-500">Success Rate</span>
          <div className="mt-1 text-2xl font-bold text-emerald-600">
            {successRate}%
          </div>
          <div className="text-xs text-slate-400">
            {completedRuns}/{totalRuns} runs
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <span className="text-xs text-slate-500">Total Runs</span>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {totalRuns}
          </div>
          <div className="text-xs text-slate-400">Last 20 shown</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <span className="text-xs text-slate-500">Config</span>
          <div className="mt-1 text-sm font-semibold text-slate-900">
            {status.enabled ? "Enabled" : "Disabled"}
          </div>
          <div className="text-xs text-slate-400">
            <code>{status.ingest_cron}</code>
          </div>
        </div>
      </div>

      {/* Scheduled Tasks */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Scheduled Tasks
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {status.scheduled_tasks.map((task) => (
            <div
              key={task.name}
              className="rounded-2xl border border-slate-200 bg-white p-5"
            >
              <h3 className="text-sm font-semibold text-slate-900">
                {task.name}
              </h3>
              <code className="mt-1 block text-xs text-slate-500">
                {task.cron}
              </code>
              <p className="mt-2 text-xs text-slate-600">{task.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Job Sources */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Job Sources
        </h2>
        <div className="flex flex-wrap gap-2">
          {status.job_sources.map((source) => (
            <span
              key={source}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
            >
              {source}
            </span>
          ))}
        </div>
      </div>

      {/* Trigger Button */}
      <div>
        <button
          onClick={handleTrigger}
          disabled={triggering}
          className={`rounded-lg px-5 py-2 text-sm font-semibold text-white ${
            triggering
              ? "cursor-not-allowed bg-slate-400"
              : "bg-slate-900 hover:bg-slate-800"
          }`}
        >
          {triggering ? "Triggering..." : "Run Ingestion Now"}
        </button>
      </div>

      {/* Run History */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Run History
        </h2>
        {runs.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
            No runs found.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-slate-500">
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Error</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="border-b border-slate-100 last:border-0"
                  >
                    <td className="px-4 py-3 font-mono text-slate-600">
                      {run.id}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusColor(run.status)}`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatTime(run.created_at)}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatDuration(run.created_at, run.updated_at)}
                    </td>
                    <td
                      className="max-w-xs truncate px-4 py-3 text-red-600"
                      title={run.error_message ?? ""}
                    >
                      {run.error_message ?? "-"}
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
