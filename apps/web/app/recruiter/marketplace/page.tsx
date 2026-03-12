"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { parseApiError } from "../../lib/api-error";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface MarketplaceJob {
  id: number;
  title: string;
  company: string | null;
  location: string | null;
  remote_flag: boolean | null;
  salary_min: number | null;
  salary_max: number | null;
  currency: string | null;
  source: string | null;
  posted_at: string | null;
  description_text: string | null;
}

const SOURCE_COLORS: Record<string, string> = {
  remotive: "bg-purple-100 text-purple-700",
  themuse: "bg-blue-100 text-blue-700",
  jooble: "bg-amber-100 text-amber-700",
  recruiter: "bg-emerald-100 text-emerald-700",
  employer: "bg-cyan-100 text-cyan-700",
};

export default function MarketplacePage() {
  const [jobs, setJobs] = useState<MarketplaceJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [activeSearch, setActiveSearch] = useState("");
  const [activeLocation, setActiveLocation] = useState("");
  const [activeRemote, setActiveRemote] = useState(false);

  function fetchJobs(pg: number, q: string, loc: string, remote: boolean) {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("page", pg.toString());
    params.set("page_size", pageSize.toString());
    if (q) params.set("q", q);
    if (loc) params.set("location", loc);
    if (remote) params.set("remote_only", "true");

    fetch(`${API_BASE}/api/recruiter/marketplace/jobs?${params}`, {
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(parseApiError(data, "Failed to load jobs"));
        }
        return res.json();
      })
      .then((data) => {
        setJobs(data.jobs);
        setTotal(data.total);
        setError("");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchJobs(page, activeSearch, activeLocation, activeRemote);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, activeSearch, activeLocation, activeRemote]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setActiveSearch(search);
    setActiveLocation(location);
    setActiveRemote(remoteOnly);
  }

  const totalPages = Math.ceil(total / pageSize);

  function formatSalary(min: number | null, max: number | null, currency: string | null) {
    if (!min && !max) return null;
    const c = currency || "USD";
    const fmt = (n: number) =>
      n >= 1000 ? `${Math.round(n / 1000)}k` : n.toString();
    if (min && max) return `${fmt(min)}-${fmt(max)} ${c}`;
    if (min) return `${fmt(min)}+ ${c}`;
    return `Up to ${fmt(max!)} ${c}`;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Job Marketplace</h1>
        <p className="mt-1 text-sm text-slate-500">
          Browse {total.toLocaleString()} jobs from multiple sources. Find matching candidates from your pipeline.
        </p>
      </div>

      {/* Search & Filters */}
      <form onSubmit={handleSearch} className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <label className="mb-1 block text-xs font-medium text-slate-600">Search</label>
          <input
            type="text"
            placeholder="Job title or company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
        </div>
        <div className="min-w-[160px]">
          <label className="mb-1 block text-xs font-medium text-slate-600">Location</label>
          <input
            type="text"
            placeholder="e.g. New York"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
        </div>
        <label className="flex items-center gap-2 pb-1">
          <input
            type="checkbox"
            checked={remoteOnly}
            onChange={(e) => setRemoteOnly(e.target.checked)}
            className="rounded border-slate-300"
          />
          <span className="text-sm text-slate-600">Remote only</span>
        </label>
        <button
          type="submit"
          className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Search
        </button>
      </form>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Job List */}
      {loading ? (
        <div className="py-12 text-center text-sm text-slate-500">Loading jobs...</div>
      ) : jobs.length === 0 ? (
        <div className="py-12 text-center text-sm text-slate-500">
          No jobs found. Try adjusting your search.
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Link
              key={job.id}
              href={`/recruiter/marketplace/${job.id}`}
              className="block rounded-lg border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-slate-900 truncate">
                    {job.title}
                  </h3>
                  <p className="mt-0.5 text-sm text-slate-600">
                    {job.company || "Unknown Company"}
                    {job.location && ` \u00b7 ${job.location}`}
                    {job.remote_flag && (
                      <span className="ml-2 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                        Remote
                      </span>
                    )}
                  </p>
                  {job.description_text && (
                    <p className="mt-1 text-xs text-slate-400 line-clamp-2">
                      {job.description_text}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 text-right shrink-0">
                  {job.source && (
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${SOURCE_COLORS[job.source] || "bg-slate-100 text-slate-600"}`}
                    >
                      {job.source}
                    </span>
                  )}
                  {formatSalary(job.salary_min, job.salary_max, job.currency) && (
                    <span className="text-xs font-medium text-slate-700">
                      {formatSalary(job.salary_min, job.salary_max, job.currency)}
                    </span>
                  )}
                  {job.posted_at && (
                    <span className="text-xs text-slate-400">
                      {new Date(job.posted_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">
            Page {page} of {totalPages} ({total.toLocaleString()} jobs)
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
