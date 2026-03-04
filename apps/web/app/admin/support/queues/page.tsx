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

type Diagnosis = { explanation: string; remedy: string };

const ERROR_PATTERNS: { test: (e: string) => boolean; diagnosis: Diagnosis }[] =
  [
    {
      test: (e) =>
        /ConnectionRefused|Connection refused|ECONNREFUSED/i.test(e),
      diagnosis: {
        explanation:
          "The worker couldn't connect to an external service (database, Redis, or API).",
        remedy:
          "Check that Postgres and Redis containers are running. Restart infra with docker compose up -d.",
      },
    },
    {
      test: (e) => /TimeoutError|timed out|deadline exceeded/i.test(e),
      diagnosis: {
        explanation:
          "The job took too long to complete and was killed.",
        remedy:
          "Retry the job. If it keeps timing out, the external API may be down or overloaded.",
      },
    },
    {
      test: (e) =>
        /ANTHROPIC_API_KEY|No LLM API keys|AuthenticationError.*anthropic/i.test(
          e,
        ),
      diagnosis: {
        explanation: "The AI/LLM API key is missing or invalid.",
        remedy:
          "Check that ANTHROPIC_API_KEY is set correctly in the API .env file.",
      },
    },
    {
      test: (e) => /rate.?limit|429|RateLimitError/i.test(e),
      diagnosis: {
        explanation: "The external API rate limit was hit.",
        remedy:
          "Wait a few minutes and retry. Consider reducing the number of concurrent jobs.",
      },
    },
    {
      test: (e) =>
        /UniqueViolation|duplicate key|IntegrityError/i.test(e),
      diagnosis: {
        explanation:
          "A duplicate record already exists in the database.",
        remedy:
          "Usually safe to ignore — the data already exists. Retrying should skip the duplicate.",
      },
    },
    {
      test: (e) =>
        /FileNotFoundError|No such file|file.*not found/i.test(e),
      diagnosis: {
        explanation:
          "A required file (resume or document) is missing from storage.",
        remedy:
          "The uploaded file may have been deleted. The user may need to re-upload their document.",
      },
    },
    {
      test: (e) => /LibreOffice|conversion failed/i.test(e),
      diagnosis: {
        explanation:
          "Document format conversion failed (e.g. .doc to PDF).",
        remedy:
          "The uploaded file may be corrupted. Ask the user to re-upload in PDF format.",
      },
    },
    {
      test: (e) => /not a JSON|JSON.*pars|JSONDecodeError/i.test(e),
      diagnosis: {
        explanation:
          "The AI returned a response that couldn't be parsed.",
        remedy:
          "Retry the job — AI responses vary and this is usually transient. If persistent, check the prompt template.",
      },
    },
    {
      test: (e) =>
        /OperationalError|connection pool|too many clients/i.test(e),
      diagnosis: {
        explanation:
          "Database connection issue — the pool may be exhausted or Postgres is unreachable.",
        remedy:
          "Check that Postgres is running. You may need to restart the API server to reset connections.",
      },
    },
    {
      test: (e) => /stripe/i.test(e),
      diagnosis: {
        explanation: "A payment processing error occurred with Stripe.",
        remedy:
          "Check Stripe API keys and webhook configuration in the .env file.",
      },
    },
    {
      test: (e) => /embedding|dimension|vector/i.test(e),
      diagnosis: {
        explanation: "Embedding generation or vector storage failed.",
        remedy:
          "Check the EMBEDDING_PROVIDER setting in the .env file and ensure the embedding service is available.",
      },
    },
    {
      test: (e) => /RESEND|email|smtp/i.test(e),
      diagnosis: {
        explanation: "Email delivery failed.",
        remedy:
          "Check that RESEND_API_KEY is configured and the email service is reachable.",
      },
    },
  ];

function diagnoseFailure(
  _funcName: string | null,
  error: string | null,
): Diagnosis {
  if (!error) {
    return {
      explanation: "No error details available.",
      remedy: "Check the API logs for more information.",
    };
  }
  for (const { test, diagnosis } of ERROR_PATTERNS) {
    if (test(error)) return diagnosis;
  }
  // Show actual error snippet instead of generic message
  const snippet = error.length > 200 ? error.slice(0, 200) + "..." : error;
  return {
    explanation: snippet,
    remedy:
      "Review the raw error below to determine root cause. If this error repeats across multiple jobs, it likely requires a code fix.",
  };
}

function FailedJobCard({ job }: { job: FailedJob }) {
  const [showRaw, setShowRaw] = useState(false);
  const diagnosis = diagnoseFailure(job.func_name, job.error);

  return (
    <div className="rounded-xl border border-red-100 bg-white p-3">
      {/* Header */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-mono text-slate-500">
            {job.job_id.substring(0, 12)}
          </span>
          <span className="font-medium text-slate-700">
            {job.func_name ?? "-"}
          </span>
        </div>
        <span className="text-slate-400">{job.ended_at ?? "-"}</span>
      </div>

      {/* Explanation */}
      <div className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs">
        <span className="font-semibold text-amber-800">What happened: </span>
        <span className="text-amber-700">{diagnosis.explanation}</span>
      </div>

      {/* Remedy */}
      <div className="mt-1.5 rounded-lg bg-slate-50 px-3 py-2 text-xs">
        <span className="font-semibold text-slate-700">Suggested fix: </span>
        <span className="text-slate-600">{diagnosis.remedy}</span>
      </div>

      {/* Raw error toggle */}
      {job.error && (
        <div className="mt-2">
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="text-[11px] font-medium text-slate-400 hover:text-slate-600"
          >
            {showRaw ? "Hide" : "Show"} raw error
          </button>
          {showRaw && (
            <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-red-50 p-2 font-mono text-[11px] text-red-700">
              {job.error}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function QueueCard({
  queue,
  isSelected,
  onSelect,
}: {
  queue: QueueDetail;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const hasFailed = queue.failed > 0;

  return (
    <div
      onClick={onSelect}
      className={`cursor-pointer rounded-2xl border bg-white p-5 transition ${
        isSelected
          ? "border-blue-400 ring-2 ring-blue-400"
          : hasFailed
            ? "border-red-300 hover:border-red-400"
            : "border-slate-200 hover:border-slate-300"
      }`}
    >
      <h3 className="text-sm font-semibold text-slate-900">{queue.name}</h3>

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
    </div>
  );
}

type ErrorGroup = {
  explanation: string;
  remedy: string;
  jobs: FailedJob[];
};

function groupFailedJobs(jobs: FailedJob[]): ErrorGroup[] {
  const groups = new Map<string, ErrorGroup>();
  for (const job of jobs) {
    const diagnosis = diagnoseFailure(job.func_name, job.error);
    const key = diagnosis.explanation;
    const existing = groups.get(key);
    if (existing) {
      existing.jobs.push(job);
    } else {
      groups.set(key, {
        explanation: diagnosis.explanation,
        remedy: diagnosis.remedy,
        jobs: [job],
      });
    }
  }
  // Sort by count descending
  return Array.from(groups.values()).sort(
    (a, b) => b.jobs.length - a.jobs.length,
  );
}

function FailedJobsSection({
  queue,
  onRetry,
}: {
  queue: QueueDetail;
  onRetry: () => void;
}) {
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const groups = groupFailedJobs(queue.failed_jobs);
  const showing = queue.failed_jobs.length;
  const total = queue.failed;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            Failed Jobs &mdash; {queue.name}
          </h2>
          {total > showing && (
            <p className="mt-0.5 text-xs text-slate-500">
              Showing {showing} of {total} failed jobs
            </p>
          )}
        </div>
        <button
          onClick={onRetry}
          className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700"
        >
          Retry All
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {groups.map((group) => {
          const isExpanded = expandedGroup === group.explanation;
          return (
            <div
              key={group.explanation}
              className="rounded-2xl border border-red-100 bg-white"
            >
              {/* Group header */}
              <button
                onClick={() =>
                  setExpandedGroup(isExpanded ? null : group.explanation)
                }
                className="flex w-full items-center justify-between p-4 text-left"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
                      {group.jobs.length}
                    </span>
                    <span className="text-sm font-medium text-slate-800">
                      {group.explanation.length > 120
                        ? group.explanation.slice(0, 120) + "..."
                        : group.explanation}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {group.remedy}
                  </p>
                </div>
                <span className="ml-2 text-xs text-slate-400">
                  {isExpanded ? "Hide" : "Show"} jobs
                </span>
              </button>

              {/* Expanded job list */}
              {isExpanded && (
                <div className="border-t border-red-50 px-4 pb-4 pt-2">
                  <div className="grid gap-3 md:grid-cols-2">
                    {group.jobs.map((fj) => (
                      <FailedJobCard key={fj.job_id} job={fj} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function QueueMonitorPage() {
  const router = useRouter();
  const [data, setData] = useState<QueueData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [selectedQueue, setSelectedQueue] = useState<string | null>(null);

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

  // Auto-select the first queue with failures, or the first queue overall
  useEffect(() => {
    if (!data || data.queues.length === 0) return;
    // Don't override if the user already selected a valid queue
    if (selectedQueue && data.queues.some((q) => q.name === selectedQueue))
      return;
    const withFailures = data.queues.find((q) => q.failed > 0);
    setSelectedQueue(withFailures ? withFailures.name : data.queues[0].name);
  }, [data, selectedQueue]);

  const selectedQueueData = data?.queues.find(
    (q) => q.name === selectedQueue,
  );

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
          <QueueCard
            key={q.name}
            queue={q}
            isSelected={selectedQueue === q.name}
            onSelect={() => setSelectedQueue(q.name)}
          />
        ))}
      </div>

      {data.queues.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          No queues found.
        </div>
      )}

      {/* Bottom section: failed jobs for the selected queue */}
      {selectedQueueData && selectedQueueData.failed_jobs.length > 0 && (
        <FailedJobsSection
          queue={selectedQueueData}
          onRetry={() => handleRetry(selectedQueueData.name)}
        />
      )}
    </div>
  );
}
