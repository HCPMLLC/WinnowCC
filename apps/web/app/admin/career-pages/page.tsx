"use client";

import { useCallback, useEffect, useState } from "react";

type CareerPage = {
  id: string;
  tenant_type: string;
  tenant_id: number;
  owner_name: string | null;
  owner_email: string | null;
  company: string | null;
  name: string;
  slug: string;
  custom_domain: string | null;
  custom_domain_verified: boolean;
  published: boolean;
  view_count: number;
  application_count: number;
  created_at: string | null;
  published_at: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const formatDate = (isoString: string | null): string => {
  if (!isoString) return "\u2014";
  return new Date(isoString).toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
};

export default function AdminCareerPagesPage() {
  const [pages, setPages] = useState<CareerPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "employer" | "recruiter">("all");

  const fetchPages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/career-pages`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CareerPage[] = await res.json();
      setPages(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load career pages");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPages();
  }, [fetchPages]);

  const filtered =
    filter === "all" ? pages : pages.filter((p) => p.tenant_type === filter);

  const published = filtered.filter((p) => p.published).length;
  const withDomain = filtered.filter((p) => p.custom_domain).length;
  const totalViews = filtered.reduce((s, p) => s + p.view_count, 0);
  const totalApps = filtered.reduce((s, p) => s + p.application_count, 0);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Career Pages</h1>
          <p className="mt-1 text-sm text-slate-500">
            All career pages across employers and recruiters
          </p>
        </div>
        <button
          onClick={fetchPages}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-slate-500">Total</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {filtered.length}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-slate-500">
            Published
          </p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">
            {published}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-slate-500">Views</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {totalViews.toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-slate-500">
            Applications
          </p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {totalApps.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-2">
        {(["all", "employer", "recruiter"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              filter === f
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {f === "all"
              ? `All (${pages.length})`
              : `${f.charAt(0).toUpperCase() + f.slice(1)}s (${pages.filter((p) => p.tenant_type === f).length})`}
          </button>
        ))}
      </div>

      {loading && (
        <p className="py-8 text-center text-slate-400">Loading...</p>
      )}
      {error && (
        <p className="py-8 text-center text-red-500">Error: {error}</p>
      )}

      {!loading && !error && filtered.length === 0 && (
        <p className="py-8 text-center text-slate-400">No career pages found</p>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">URL</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Views</th>
                <th className="px-4 py-3 text-right">Apps</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((page) => (
                <tr key={page.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {page.name}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-slate-900">
                      {page.company || page.owner_name || "\u2014"}
                    </div>
                    {page.owner_email && (
                      <div className="text-xs text-slate-400">
                        {page.owner_email}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        page.tenant_type === "employer"
                          ? "bg-blue-50 text-blue-700"
                          : "bg-purple-50 text-purple-700"
                      }`}
                    >
                      {page.tenant_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-xs text-slate-600">
                      winnowcc.ai/careers/{page.slug}
                    </div>
                    {page.custom_domain && (
                      <div className="mt-0.5 flex items-center gap-1 text-xs">
                        <span className="text-slate-500">
                          {page.custom_domain}
                        </span>
                        <span
                          className={`inline-block h-1.5 w-1.5 rounded-full ${
                            page.custom_domain_verified
                              ? "bg-emerald-500"
                              : "bg-amber-400"
                          }`}
                          title={
                            page.custom_domain_verified
                              ? "Verified"
                              : "Pending"
                          }
                        />
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        page.published
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {page.published ? "Published" : "Draft"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {page.view_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {page.application_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {formatDate(page.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {withDomain > 0 && (
        <p className="mt-3 text-xs text-slate-400">
          {withDomain} page{withDomain !== 1 ? "s" : ""} with custom domain
          configured
        </p>
      )}
    </div>
  );
}
