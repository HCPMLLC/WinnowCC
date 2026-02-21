"use client";

import { Fragment, useEffect, useState, useCallback } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type CompanyJob = {
  id: number;
  job_id_external: string | null;
  title: string;
  status: string;
  job_category: string | null;
  location: string | null;
  remote_policy: string | null;
  posted_at: string | null;
  close_date: string | null;
  view_count: number | null;
  matched_candidates_count: number;
  application_count: number | null;
  poster_email: string | null;
  created_at: string | null;
};

type SortField =
  | "job_id_external"
  | "title"
  | "status"
  | "job_category"
  | "location"
  | "posted_at"
  | "close_date"
  | "view_count"
  | "matched_candidates_count"
  | "application_count"
  | "created_at";

type GroupBy = "poster_email" | "status" | "job_category" | "location" | "";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800",
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  closed: "bg-red-100 text-red-800",
};

const COLUMNS: { key: SortField; label: string }[] = [
  { key: "job_id_external", label: "Job ID" },
  { key: "title", label: "Title" },
  { key: "status", label: "Status" },
  { key: "job_category", label: "Category" },
  { key: "location", label: "Location" },
  { key: "posted_at", label: "Posted" },
  { key: "close_date", label: "Close Date" },
  { key: "view_count", label: "Views" },
  { key: "matched_candidates_count", label: "Matches" },
  { key: "application_count", label: "Apps" },
];

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

export default function CompanyJobsPage() {
  const [jobs, setJobs] = useState<CompanyJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sortBy, setSortBy] = useState<SortField>("close_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [groupBy, setGroupBy] = useState<GroupBy>("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        sort_dir: sortDir,
        page: String(page),
        page_size: String(pageSize),
      });
      if (groupBy) params.set("group_by", groupBy);
      if (statusFilter) params.set("status", statusFilter);

      const res = await fetch(
        `${API_BASE}/api/employer/jobs/company?${params}`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("Failed to load company jobs.");
      const data = await res.json();
      setJobs(data.items);
      setTotal(data.total);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortDir, groupBy, statusFilter, page]);

  useEffect(() => {
    void fetchJobs();
  }, [fetchJobs]);

  const handleSort = (col: SortField) => {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  // Group rows
  let groupedJobs: { label: string; rows: CompanyJob[] }[] = [];
  if (groupBy) {
    const map = new Map<string, CompanyJob[]>();
    for (const job of jobs) {
      const key =
        (groupBy === "poster_email"
          ? job.poster_email
          : groupBy === "status"
            ? job.status
            : groupBy === "job_category"
              ? job.job_category
              : job.location) || "Unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(job);
    }
    groupedJobs = Array.from(map.entries()).map(([label, rows]) => ({
      label,
      rows,
    }));
  }

  const renderSortArrow = (col: SortField) => {
    if (sortBy !== col) return null;
    return (
      <span className="ml-1 text-blue-400">
        {sortDir === "asc" ? "\u25B2" : "\u25BC"}
      </span>
    );
  };

  const renderRow = (job: CompanyJob) => (
    <tr key={job.id} className="border-t border-slate-100 hover:bg-slate-50">
      <td className="px-4 py-3 text-sm text-slate-500 font-mono">
        {job.job_id_external || "\u2014"}
      </td>
      <td className="px-4 py-3 text-sm font-medium text-slate-900">
        <Link
          href={`/employer/jobs/${job.id}`}
          className="hover:text-blue-600 hover:underline"
        >
          {job.title}
        </Link>
        {job.remote_policy && (
          <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 capitalize">
            {job.remote_policy}
          </span>
        )}
      </td>
      <td className="px-4 py-3">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}
        >
          {job.status}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {job.job_category || "\u2014"}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {job.location || "\u2014"}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {formatDate(job.posted_at)}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {job.close_date
          ? new Date(job.close_date + "T00:00:00").toLocaleDateString()
          : "\u2014"}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600 text-right">
        {job.view_count ?? 0}
      </td>
      <td className="px-4 py-3 text-sm text-right">
        {job.matched_candidates_count > 0 ? (
          <span className="font-medium text-emerald-600">
            {job.matched_candidates_count}
          </span>
        ) : (
          <span className="text-slate-400">0</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600 text-right">
        {job.application_count ?? 0}
      </td>
    </tr>
  );

  if (loading && jobs.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-slate-500">Loading company jobs...</p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Company Jobs</h1>
          <p className="mt-1 text-sm text-slate-500">
            All postings across your organization ({total})
          </p>
        </div>
        <Link
          href="/employer/jobs"
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          My Jobs
        </Link>
      </div>

      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {/* Status filter */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-700">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        {/* Group by */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-700">
            Group by:
          </label>
          <select
            value={groupBy}
            onChange={(e) => {
              setGroupBy(e.target.value as GroupBy);
              setPage(1);
            }}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            <option value="">None</option>
            <option value="poster_email">Posted By</option>
            <option value="status">Status</option>
            <option value="job_category">Category</option>
            <option value="location">Location</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left">
          <thead className="bg-slate-50">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className={`cursor-pointer px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-900 ${
                    col.key === "view_count" || col.key === "matched_candidates_count" || col.key === "application_count"
                      ? "text-right"
                      : ""
                  }`}
                >
                  {col.label}
                  {renderSortArrow(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td
                  colSpan={COLUMNS.length}
                  className="px-4 py-12 text-center text-slate-500"
                >
                  No company jobs found.
                </td>
              </tr>
            ) : groupBy && groupedJobs.length > 0 ? (
              groupedJobs.map((group) => (
                <Fragment key={group.label}>
                  <tr className="bg-slate-100">
                    <td
                      colSpan={COLUMNS.length}
                      className="px-4 py-2 text-sm font-semibold text-slate-700"
                    >
                      {group.label}{" "}
                      <span className="font-normal text-slate-400">
                        ({group.rows.length})
                      </span>
                    </td>
                  </tr>
                  {group.rows.map(renderRow)}
                </Fragment>
              ))
            ) : (
              jobs.map(renderRow)
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-slate-600">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
