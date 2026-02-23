"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type AuditEntry = {
  id: number;
  source: string;
  action: string;
  actor: string | null;
  user_email: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

type AuditData = {
  entries: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function AuditLogPage() {
  const router = useRouter();
  const [data, setData] = useState<AuditData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(
        `${API}/api/admin/support/audit-log?page=${page}&page_size=${pageSize}&source=${source}`,
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
      if (!res.ok) throw new Error("Failed to load audit log");
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [router, source, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-semibold">Audit Log</h1>
        <p className="mt-1 text-sm text-slate-600">
          Unified audit trail from trust and compliance sources.
        </p>
      </header>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold text-slate-500">Source:</span>
        {["all", "trust", "compliance"].map((s) => (
          <button
            key={s}
            onClick={() => {
              setSource(s);
              setPage(1);
            }}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              source === s
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!data && !error && (
        <p className="text-sm text-slate-500">Loading...</p>
      )}

      {data && (
        <>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
              <span>{data.total} total entries</span>
              <span>
                Page {data.page} of {totalPages || 1}
              </span>
            </div>

            {data.entries.length === 0 ? (
              <p className="text-sm text-slate-400">No audit entries found.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-slate-500">
                      <th className="pb-2 pr-3">Timestamp</th>
                      <th className="pb-2 pr-3">Source</th>
                      <th className="pb-2 pr-3">Action</th>
                      <th className="pb-2 pr-3">Actor</th>
                      <th className="pb-2 pr-3">User</th>
                      <th className="pb-2">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.map((entry) => (
                      <tr
                        key={`${entry.source}-${entry.id}`}
                        className="border-b border-slate-100"
                      >
                        <td className="py-2 pr-3 whitespace-nowrap text-slate-500">
                          {new Date(entry.created_at).toLocaleString()}
                        </td>
                        <td className="py-2 pr-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                              entry.source === "trust"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-purple-100 text-purple-800"
                            }`}
                          >
                            {entry.source}
                          </span>
                        </td>
                        <td className="py-2 pr-3 font-medium text-slate-700">
                          {entry.action}
                        </td>
                        <td className="py-2 pr-3 text-slate-600">
                          {entry.actor ?? "-"}
                        </td>
                        <td className="py-2 pr-3 text-slate-600">
                          {entry.user_email ?? "-"}
                        </td>
                        <td className="max-w-xs truncate py-2 text-slate-500">
                          {entry.details
                            ? JSON.stringify(entry.details).substring(0, 80)
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-xs text-slate-500">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
