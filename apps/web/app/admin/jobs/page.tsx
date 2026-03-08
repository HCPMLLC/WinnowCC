"use client";

import { Fragment, useEffect, useState, useCallback } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type AdminJob = {
  id: number;
  title: string;
  company: string;
  location: string | null;
  source: string;
  remote_flag: boolean | null;
  posted_at: string | null;
  application_deadline: string | null;
  hiring_manager_name: string | null;
  hiring_manager_email: string | null;
  ingested_at: string | null;
};

type SortField =
  | "title"
  | "company"
  | "location"
  | "source"
  | "posted_at"
  | "application_deadline"
  | "hiring_manager_name"
  | "ingested_at";

type GroupBy = "company" | "location" | "source" | "";

const COLUMNS: { key: SortField; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "company", label: "Company" },
  { key: "location", label: "Location" },
  { key: "hiring_manager_name", label: "Hiring Contact" },
  { key: "source", label: "Source" },
  { key: "posted_at", label: "Posted" },
  { key: "application_deadline", label: "Deadline" },
  { key: "ingested_at", label: "Ingested" },
];

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sortBy, setSortBy] = useState<SortField>("ingested_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [groupBy, setGroupBy] = useState<GroupBy>("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
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
      if (search) params.set("search", search);

      const res = await fetch(`${API_BASE}/api/admin/jobs/all?${params}`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to load jobs.");
      const data = await res.json();
      setJobs(data.items);
      setTotal(data.total);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortDir, groupBy, search, page]);

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

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  // Group rows by the selected field
  let groupedJobs: { label: string; rows: AdminJob[] }[] = [];
  if (groupBy) {
    const map = new Map<string, AdminJob[]>();
    for (const job of jobs) {
      const key =
        (groupBy === "company"
          ? job.company
          : groupBy === "location"
            ? job.location
            : job.source) || "Unknown";
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
      <span className="ml-1 text-amber-400">
        {sortDir === "asc" ? "\u25B2" : "\u25BC"}
      </span>
    );
  };

  const renderRow = (job: AdminJob) => (
    <tr key={job.id} className="border-t border-slate-100 hover:bg-slate-50">
      <td className="px-4 py-3 text-sm font-medium text-slate-900">
        {job.title}
        {job.remote_flag && (
          <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
            Remote
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">{job.company}</td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {job.location || "\u2014"}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {job.hiring_manager_name || "\u2014"}
        {job.hiring_manager_email && (
          <span className="ml-1 text-xs text-slate-400">
            ({job.hiring_manager_email})
          </span>
        )}
      </td>
      <td className="px-4 py-3">
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
          {job.source}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {formatDate(job.posted_at)}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {formatDate(job.application_deadline)}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {formatDateTime(job.ingested_at)}
      </td>
    </tr>
  );

  if (loading && jobs.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <p className="text-slate-500">Loading jobs...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">All Jobs</h1>
            <p className="mt-1 text-sm text-slate-500">
              {total.toLocaleString()} total ingested jobs
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Search title or company..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
            >
              Search
            </button>
            {search && (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setSearchInput("");
                  setPage(1);
                }}
                className="text-sm text-slate-500 hover:text-slate-700"
              >
                Clear
              </button>
            )}
          </form>

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
              <option value="company">Company</option>
              <option value="location">Location</option>
              <option value="source">Source</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left">
            <thead className="bg-slate-50">
              <tr>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className="cursor-pointer px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-900"
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
                    No jobs found.
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
    </div>
  );
}

