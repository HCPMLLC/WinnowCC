"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type FailedJob = {
  job_id: string;
  func_name: string | null;
  error: string | null;
  enqueued_at: string | null;
  ended_at: string | null;
};

type QueueDetail = {
  name: string;
  pending: number;
  started: number;
  failed: number;
  deferred: number;
  failed_jobs: FailedJob[];
};

type QueueData = {
  redis_connected: boolean;
  queues: QueueDetail[];
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function QueueCard({
  queue,
  onRetry,
}: {
  queue: QueueDetail;
  onRetry: (name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasFailed = queue.failed > 0;

  return (
    <div
      className={`rounded-2xl border bg-white p-5 ${hasFailed ? "border-red-300" : "border-slate-200"}`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">{queue.name}</h3>
        {hasFailed && (
          <button
            onClick={() => onRetry(queue.name)}
            className="rounded-lg bg-red-600 px-3 py-1 text-xs font-semibold text-white"
          >
            Retry All
          </button>
        )}
      </div>

      <div className="mt-3 flex gap-4 text-sm">
        <div>
          <span className="text-xs text-slate-500">Pending</span>
          <div className="text-lg font-bold text-blue-600">{queue.pending}</div>
        </div>
        <div>
          <span className="text-xs text-slate-500">Started</span>
          <div className="text-lg font-bold text-emerald-600">
            {queue.started}
          </div>
        </div>
        <div>
          <span className="text-xs text-slate-500">Failed</span>
          <div
            className={`text-lg font-bold ${hasFailed ? "text-red-600" : "text-slate-400"}`}
          >
            {queue.failed}
          </div>
        </div>
        <div>
          <span className="text-xs text-slate-500">Deferred</span>
          <div className="text-lg font-bold text-slate-400">
            {queue.deferred}
          </div>
        </div>
      </div>

      {hasFailed && (
        <div className="mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            {expanded ? "Hide" : "Show"} failed jobs ({queue.failed_jobs.length})
          </button>
          {expanded && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="pb-1 pr-3">Job ID</th>
                    <th className="pb-1 pr-3">Function</th>
                    <th className="pb-1 pr-3">Error</th>
                    <th className="pb-1">Ended</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.failed_jobs.map((fj) => (
                    <tr key={fj.job_id} className="border-b border-slate-100">
                      <td className="py-1 pr-3 font-mono text-slate-600">
                        {fj.job_id.substring(0, 12)}...
                      </td>
                      <td className="py-1 pr-3">{fj.func_name ?? "-"}</td>
                      <td
                        className="max-w-xs truncate py-1 pr-3 text-red-600"
                        title={fj.error ?? ""}
                      >
                        {fj.error ?? "-"}
                      </td>
                      <td className="py-1 text-slate-500">
                        {fj.ended_at ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function QueueMonitorPage() {
  const router = useRouter();
  const [data, setData] = useState<QueueData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/support/queue-monitor`, {
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
      if (!res.ok) throw new Error("Failed to load queue data");
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRetry = async (queueName: string) => {
    setActionMsg(null);
    try {
      const res = await fetch(
        `${API}/api/admin/support/actions/retry-queue/${queueName}`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok) throw new Error("Retry failed");
      const result = await res.json();
      setActionMsg(result.message);
      // Reload data
      void load();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Retry failed");
    }
  };

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

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Queue Monitor</h1>
          <p className="mt-1 text-sm text-slate-600">
            Redis{" "}
            <span
              className={`font-semibold ${data.redis_connected ? "text-emerald-600" : "text-red-600"}`}
            >
              {data.redis_connected ? "connected" : "disconnected"}
            </span>
          </p>
        </div>
        <button
          onClick={() => load()}
          className="rounded-lg bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200"
        >
          Refresh
        </button>
      </header>

      {actionMsg && (
        <div className="rounded-xl bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {actionMsg}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data.queues.map((q) => (
          <QueueCard key={q.name} queue={q} onRetry={handleRetry} />
        ))}
      </div>

      {data.queues.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          No queues found.
        </div>
      )}
    </div>
  );
}
