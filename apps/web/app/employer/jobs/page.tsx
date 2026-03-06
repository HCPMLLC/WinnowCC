"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Job {
  id: number;
  title: string;
  status: string;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  job_category: string | null;
  close_date: string | null;
  view_count: number;
  matched_candidates_count: number;
  application_count: number;
  created_at: string;
  posted_at: string | null;
  archived: boolean;
  archived_reason: string | null;
  archived_at: string | null;
  job_id_external: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800",
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  closed: "bg-red-100 text-red-800",
};

export default function JobsPage() {
  const [viewTab, setViewTab] = useState<"active" | "archived">("active");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [archivedJobs, setArchivedJobs] = useState<Job[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function fetchJobs(archived: boolean) {
    try {
      const url = new URL(`${API_BASE}/api/employer/jobs`);
      url.searchParams.set("archived", String(archived));
      if (!archived && statusFilter) {
        url.searchParams.set("status", statusFilter);
      }
      const res = await fetch(url.toString(), { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        if (archived) {
          setArchivedJobs(data);
        } else {
          setJobs(data);
        }
      }
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    }
  }

  useEffect(() => {
    setIsLoading(true);
    fetchJobs(false).finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchJobs is a closure over statusFilter, already tracked
  }, [statusFilter]);

  useEffect(() => {
    if (viewTab === "archived") {
      fetchJobs(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchJobs is a closure over statusFilter, already tracked
  }, [viewTab]);

  async function unarchiveJob(jobId: number) {
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${jobId}/unarchive`,
        { method: "POST", credentials: "include" },
      );
      if (res.ok) {
        setArchivedJobs((prev) => prev.filter((j) => j.id !== jobId));
        fetchJobs(false);
      }
    } catch (err) {
      console.error("Failed to unarchive:", err);
    }
  }

  const displayedJobs = viewTab === "active" ? jobs : archivedJobs;

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Job Postings</h1>
          <p className="mt-1 text-slate-600">Manage your job listings</p>
        </div>
        <Link
          href="/employer/jobs/new"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          + Create Job
        </Link>
      </div>

      {/* Tabs */}
      <div className="mb-6 border-b border-slate-200">
        <nav className="-mb-px flex gap-4 overflow-x-auto sm:gap-8">
          <button
            onClick={() => setViewTab("active")}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              viewTab === "active"
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            Active Jobs ({jobs.length})
          </button>
          <button
            onClick={() => setViewTab("archived")}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              viewTab === "archived"
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            Archived ({archivedJobs.length})
          </button>
          <Link
            href="/employer/jobs/company"
            className="border-b-2 border-transparent py-3 px-1 text-sm font-medium text-slate-500 hover:border-slate-300 hover:text-slate-700"
          >
            Company Jobs
          </Link>
        </nav>
      </div>

      {/* Status filter (active tab only) */}
      {viewTab === "active" && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-slate-700">
              Filter by status:
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            >
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div>
      )}

      {/* Jobs List */}
      {isLoading && viewTab === "active" ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : displayedJobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-xl font-semibold text-slate-900">
            {viewTab === "active" ? "No jobs yet" : "No archived jobs"}
          </h3>
          <p className="mt-2 text-slate-600">
            {viewTab === "active"
              ? "Create your first job posting to start attracting candidates."
              : "Archived jobs will appear here."}
          </p>
          {viewTab === "active" && (
            <Link
              href="/employer/jobs/new"
              className="mt-4 inline-block rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Create Your First Job
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {displayedJobs.map((job) => (
            <div key={job.id} className="flex items-center gap-4">
              <Link href={`/employer/jobs/${job.id}`} className="flex-1">
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="mb-1 text-xs font-medium text-slate-400">
                        ID: {job.job_id_external || job.id}
                      </p>
                      <div className="mb-2 flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-slate-900">
                          {job.title}
                        </h3>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-600"}`}
                        >
                          {job.status}
                        </span>
                        {job.archived_reason && (
                          <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800">
                            {job.archived_reason}
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-4 text-sm text-slate-500">
                        {job.job_category && <span>{job.job_category}</span>}
                        {job.location && <span>{job.location}</span>}
                        {job.remote_policy && (
                          <span className="capitalize">
                            {job.remote_policy}
                          </span>
                        )}
                        {job.employment_type && (
                          <span className="capitalize">
                            {job.employment_type}
                          </span>
                        )}
                        {job.close_date && (
                          <span>
                            Deadline:{" "}
                            {new Date(
                              job.close_date + "T00:00:00",
                            ).toLocaleDateString()}
                          </span>
                        )}
                      </div>

                      <div className="mt-3 flex gap-6 text-sm text-slate-500">
                        <span>{job.view_count} views</span>
                        {job.matched_candidates_count > 0 && (
                          <span className="font-medium text-emerald-600">
                            {job.matched_candidates_count} matched
                          </span>
                        )}
                        <span>{job.application_count} applications</span>
                        <span>
                          Created{" "}
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    <svg
                      className="h-5 w-5 text-slate-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </div>
                </div>
              </Link>

              {viewTab === "archived" && (
                <button
                  onClick={() => unarchiveJob(job.id)}
                  className="shrink-0 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Unarchive
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
