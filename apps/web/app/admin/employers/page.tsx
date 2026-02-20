"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Employer = {
  id: number;
  user_id: number;
  email: string | null;
  company_name: string;
  company_size: string | null;
  industry: string | null;
  subscription_tier: string;
  subscription_status: string | null;
  contact_first_name: string | null;
  contact_last_name: string | null;
  contact_email: string | null;
  active_jobs_count: number;
  total_jobs_count: number;
  ai_parsing_used: number;
  intro_requests_used: number;
  created_at: string | null;
};

type EmployerJob = {
  id: number;
  title: string;
  status: string;
  location: string | null;
  remote_policy: string | null;
  application_count: number | null;
  view_count: number | null;
  posted_at: string | null;
  created_at: string | null;
  archived: boolean;
  archived_reason: string | null;
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

const TierBadge = ({ tier }: { tier: string }) => {
  const colors: Record<string, string> = {
    free: "bg-slate-100 text-slate-700 border-slate-200",
    starter: "bg-blue-100 text-blue-700 border-blue-200",
    pro: "bg-emerald-100 text-emerald-700 border-emerald-200",
  };
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colors[tier] || "bg-slate-100 text-slate-600"}`}
    >
      {tier}
    </span>
  );
};

export default function AdminEmployersPage() {
  const router = useRouter();
  const [employers, setEmployers] = useState<Employer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedJobs, setExpandedJobs] = useState<EmployerJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  // Tier override modal
  const [overrideTarget, setOverrideTarget] = useState<Employer | null>(null);
  const [overrideTier, setOverrideTier] = useState("free");
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);

  const loadEmployers = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/employers`, {
        credentials: "include",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 403) {
        setError("Admin access required.");
        setIsLoading(false);
        return;
      }
      if (!response.ok) throw new Error("Failed to load employers.");
      const payload = (await response.json()) as Employer[];
      setEmployers(payload);
      setSelectedIds(new Set());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to load employers."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadEmployers();
  }, [router]);

  const filteredEmployers = employers.filter((e) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      e.company_name?.toLowerCase().includes(term) ||
      e.email?.toLowerCase().includes(term) ||
      e.industry?.toLowerCase().includes(term) ||
      e.contact_email?.toLowerCase().includes(term)
    );
  });

  const toggleSelect = (userId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredEmployers.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredEmployers.map((e) => e.user_id)));
    }
  };

  const handleDelete = async () => {
    if (selectedIds.size === 0) return;
    const confirmed = window.confirm(
      `Are you sure you want to delete ${selectedIds.size} employer(s)? This action cannot be undone.`
    );
    if (!confirmed) return;

    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(`${API_BASE}/api/admin/employers/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user_ids: Array.from(selectedIds) }),
      });
      if (!response.ok) throw new Error("Failed to delete employers.");
      const result = (await response.json()) as { message: string };
      setSuccessMessage(result.message);
      await loadEmployers();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to delete employers."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const loadJobs = async (employerId: number) => {
    if (expandedId === employerId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(employerId);
    setJobsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/employers/${employerId}/jobs`,
        { credentials: "include" }
      );
      if (!response.ok) throw new Error("Failed to load jobs.");
      setExpandedJobs((await response.json()) as EmployerJob[]);
    } catch {
      setExpandedJobs([]);
    } finally {
      setJobsLoading(false);
    }
  };

  const handleTierOverride = async () => {
    if (!overrideTarget) return;
    setOverrideSubmitting(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/employers/${overrideTarget.id}/tier-override`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            subscription_tier: overrideTier,
            subscription_status: null,
          }),
        }
      );
      if (!response.ok) throw new Error("Failed to override tier.");
      setSuccessMessage(
        `Tier updated to "${overrideTier}" for ${overrideTarget.company_name}.`
      );
      setOverrideTarget(null);
      await loadEmployers();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to override tier."
      );
    } finally {
      setOverrideSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
        <h1 className="text-3xl font-semibold">Employers</h1>
        <p className="text-sm text-slate-600">Loading employers...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">All Employers</h1>
        <p className="text-sm text-slate-600">
          {employers.length} total employers
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          {successMessage}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search by company, email, industry..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        {selectedIds.size > 0 && (
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {isDeleting
              ? "Deleting..."
              : `Delete ${selectedIds.size} selected`}
          </button>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left">
                <input
                  type="checkbox"
                  checked={
                    filteredEmployers.length > 0 &&
                    selectedIds.size === filteredEmployers.length
                  }
                  onChange={toggleSelectAll}
                  className="rounded border-slate-300"
                />
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Company
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Email
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Tier
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Industry
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Jobs
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Usage
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredEmployers.map((emp) => (
              <>
                <tr
                  key={emp.id}
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => loadJobs(emp.id)}
                >
                  <td
                    className="px-3 py-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(emp.user_id)}
                      onChange={() => toggleSelect(emp.user_id)}
                      className="rounded border-slate-300"
                    />
                  </td>
                  <td className="px-3 py-2 text-sm font-medium text-slate-900">
                    {emp.company_name}
                    {emp.company_size && (
                      <span className="ml-1 text-xs text-slate-400">
                        ({emp.company_size})
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    {emp.email || "\u2014"}
                  </td>
                  <td
                    className="px-3 py-2"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOverrideTarget(emp);
                      setOverrideTier(emp.subscription_tier);
                    }}
                  >
                    <TierBadge tier={emp.subscription_tier} />
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    {emp.industry || "\u2014"}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    {emp.active_jobs_count}/{emp.total_jobs_count}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    AI:{emp.ai_parsing_used} Intro:{emp.intro_requests_used}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-500">
                    {formatDate(emp.created_at)}
                  </td>
                </tr>

                {/* Expanded row: jobs */}
                {expandedId === emp.id && (
                  <tr key={`${emp.id}-jobs`}>
                    <td colSpan={8} className="bg-slate-50 px-6 py-4">
                      <h4 className="mb-2 text-sm font-semibold text-slate-700">
                        Jobs ({expandedJobs.length})
                      </h4>
                      {jobsLoading ? (
                        <p className="text-sm text-slate-500">Loading...</p>
                      ) : expandedJobs.length === 0 ? (
                        <p className="text-sm text-slate-500">No jobs found.</p>
                      ) : (
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-xs font-medium uppercase text-slate-400">
                              <th className="pb-1 pr-4">Title</th>
                              <th className="pb-1 pr-4">Status</th>
                              <th className="pb-1 pr-4">Location</th>
                              <th className="pb-1 pr-4">Apps</th>
                              <th className="pb-1 pr-4">Views</th>
                              <th className="pb-1 pr-4">Posted</th>
                            </tr>
                          </thead>
                          <tbody>
                            {expandedJobs.map((j) => (
                              <tr key={j.id} className="border-t border-slate-100">
                                <td className="py-1 pr-4 font-medium">
                                  {j.title}
                                  {j.archived && (
                                    <span className="ml-1 text-xs text-slate-400">
                                      (archived)
                                    </span>
                                  )}
                                </td>
                                <td className="py-1 pr-4">{j.status}</td>
                                <td className="py-1 pr-4">
                                  {j.location || "\u2014"}
                                </td>
                                <td className="py-1 pr-4">
                                  {j.application_count ?? 0}
                                </td>
                                <td className="py-1 pr-4">
                                  {j.view_count ?? 0}
                                </td>
                                <td className="py-1 pr-4">
                                  {formatDate(j.posted_at)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
            {filteredEmployers.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="px-3 py-8 text-center text-sm text-slate-500"
                >
                  {searchTerm
                    ? "No employers match your search."
                    : "No employers found."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Tier Override Modal */}
      {overrideTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">
              Override Tier: {overrideTarget.company_name}
            </h3>
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Subscription Tier
              </label>
              <select
                value={overrideTier}
                onChange={(e) => setOverrideTier(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="free">Free</option>
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
              </select>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setOverrideTarget(null)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleTierOverride}
                disabled={overrideSubmitting}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {overrideSubmitting ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
