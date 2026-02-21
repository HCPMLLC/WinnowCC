"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface LogEntry {
  id: number;
  event_type: string;
  event_data: Record<string, unknown>;
  employer_job_id: number | null;
  user_id: number | null;
  created_at: string | null;
}

export default function CompliancePage() {
  const [log, setLog] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetchLog();
  }, []);

  async function fetchLog() {
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/compliance/log?limit=50`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("Failed to load compliance log");
      setLog(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setIsLoading(false);
    }
  }

  async function generateReport() {
    setReportLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/compliance/report/ofccp`,
        { credentials: "include" },
      );
      if (res.ok) setReport(await res.json());
    } catch {
      // Ignore
    } finally {
      setReportLoading(false);
    }
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
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Compliance</h1>
          <p className="mt-1 text-slate-600">
            Audit trail, OFCCP reports, and DEI recommendations
          </p>
        </div>
        <button
          onClick={generateReport}
          disabled={reportLoading}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {reportLoading ? "Generating..." : "Generate OFCCP Report"}
        </button>
      </div>

      {/* Report Output */}
      {report && (
        <div className="mb-8 rounded-xl border border-emerald-200 bg-emerald-50 p-6">
          <h2 className="mb-2 text-lg font-semibold text-emerald-900">
            OFCCP Report Generated
          </h2>
          <p className="text-sm text-emerald-700">
            Report covers {(report.total_jobs as number) ?? 0} jobs.
            Generated at{" "}
            {report.generated_at
              ? new Date(report.generated_at as string).toLocaleString()
              : "N/A"}
          </p>
          <button
            onClick={() => {
              const blob = new Blob(
                [JSON.stringify(report, null, 2)],
                { type: "application/json" },
              );
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "ofccp_report.json";
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="mt-3 rounded-lg border border-emerald-300 px-3 py-1.5 text-sm font-medium text-emerald-800 hover:bg-emerald-100"
          >
            Download JSON
          </button>
        </div>
      )}

      {/* Audit Log */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">Audit Log</h2>
        </div>
        {isLoading ? (
          <div className="space-y-3 p-6">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded bg-slate-100"
              />
            ))}
          </div>
        ) : log.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">
            No compliance events recorded yet.
          </p>
        ) : (
          <div className="divide-y divide-slate-100">
            {log.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center justify-between px-6 py-3"
              >
                <div>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                    {entry.event_type}
                  </span>
                  {entry.employer_job_id && (
                    <span className="ml-2 text-xs text-slate-500">
                      Job #{entry.employer_job_id}
                    </span>
                  )}
                </div>
                <span className="text-xs text-slate-400">
                  {entry.created_at
                    ? new Date(entry.created_at).toLocaleString()
                    : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
