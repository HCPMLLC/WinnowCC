"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Recruiter = {
  id: number;
  user_id: number;
  email: string | null;
  company_name: string;
  company_type: string | null;
  company_website: string | null;
  subscription_tier: string;
  subscription_status: string | null;
  billing_interval: string | null;
  billing_exempt: boolean;
  seats_purchased: number;
  seats_used: number;
  is_trial_active: boolean;
  trial_days_remaining: number;
  candidate_briefs_used: number;
  salary_lookups_used: number;
  job_uploads_used: number;
  intro_requests_used: number;
  resume_imports_used: number;
  outreach_enrollments_used: number;
  pipeline_count: number;
  jobs_count: number;
  clients_count: number;
  created_at: string | null;
};

type RecruiterJob = {
  id: number;
  title: string;
  status: string;
  client_company_name: string | null;
  location: string | null;
  priority: string | null;
  positions_to_fill: number;
  positions_filled: number;
  created_at: string | null;
};

type RecruiterClient = {
  id: number;
  company_name: string;
  industry: string | null;
  contact_name: string | null;
  contact_email: string | null;
  status: string;
  contract_type: string | null;
  fee_percentage: number | null;
  created_at: string | null;
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
    trial: "bg-amber-100 text-amber-700 border-amber-200",
    solo: "bg-slate-100 text-slate-700 border-slate-200",
    team: "bg-blue-100 text-blue-700 border-blue-200",
    agency: "bg-emerald-100 text-emerald-700 border-emerald-200",
  };
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colors[tier] || "bg-slate-100 text-slate-600"}`}
    >
      {tier}
    </span>
  );
};

export default function AdminRecruitersPage() {
  const router = useRouter();
  const [recruiters, setRecruiters] = useState<Recruiter[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedJobs, setExpandedJobs] = useState<RecruiterJob[]>([]);
  const [expandedClients, setExpandedClients] = useState<RecruiterClient[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  // Tier override modal
  const [overrideTarget, setOverrideTarget] = useState<Recruiter | null>(null);
  const [overrideTier, setOverrideTier] = useState("trial");
  const [overrideBillingExempt, setOverrideBillingExempt] = useState(false);
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);

  const loadRecruiters = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/recruiters`, {
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
      if (!response.ok) throw new Error("Failed to load recruiters.");
      const payload = (await response.json()) as Recruiter[];
      setRecruiters(payload);
      setSelectedIds(new Set());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to load recruiters."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadRecruiters();
  }, [router]);

  const filteredRecruiters = recruiters.filter((r) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      r.company_name?.toLowerCase().includes(term) ||
      r.email?.toLowerCase().includes(term) ||
      r.company_type?.toLowerCase().includes(term)
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
    if (selectedIds.size === filteredRecruiters.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredRecruiters.map((r) => r.user_id)));
    }
  };

  const handleDelete = async () => {
    if (selectedIds.size === 0) return;
    const confirmed = window.confirm(
      `Are you sure you want to delete ${selectedIds.size} recruiter(s)? This action cannot be undone.`
    );
    if (!confirmed) return;

    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(`${API_BASE}/api/admin/recruiters/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user_ids: Array.from(selectedIds) }),
      });
      if (!response.ok) throw new Error("Failed to delete recruiters.");
      const result = (await response.json()) as { message: string };
      setSuccessMessage(result.message);
      await loadRecruiters();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Failed to delete recruiters."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const loadDetails = async (recruiterId: number) => {
    if (expandedId === recruiterId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(recruiterId);
    setDetailLoading(true);
    try {
      const [jobsRes, clientsRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/recruiters/${recruiterId}/jobs`, {
          credentials: "include",
        }),
        fetch(`${API_BASE}/api/admin/recruiters/${recruiterId}/clients`, {
          credentials: "include",
        }),
      ]);
      setExpandedJobs(
        jobsRes.ok ? ((await jobsRes.json()) as RecruiterJob[]) : []
      );
      setExpandedClients(
        clientsRes.ok ? ((await clientsRes.json()) as RecruiterClient[]) : []
      );
    } catch {
      setExpandedJobs([]);
      setExpandedClients([]);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleTierOverride = async () => {
    if (!overrideTarget) return;
    setOverrideSubmitting(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/recruiters/${overrideTarget.id}/tier-override`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            subscription_tier: overrideTier,
            subscription_status: null,
            billing_exempt: overrideBillingExempt,
          }),
        }
      );
      if (!response.ok) throw new Error("Failed to override tier.");
      setSuccessMessage(
        `Tier updated to "${overrideTier}" for ${overrideTarget.company_name}.`
      );
      setOverrideTarget(null);
      await loadRecruiters();
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
        <h1 className="text-3xl font-semibold">Recruiters</h1>
        <p className="text-sm text-slate-600">Loading recruiters...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">All Recruiters</h1>
        <p className="text-sm text-slate-600">
          {recruiters.length} total recruiters
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
          placeholder="Search by company, email, type..."
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
                    filteredRecruiters.length > 0 &&
                    selectedIds.size === filteredRecruiters.length
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
                Seats
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Pipeline / Jobs / Clients
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Trial
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-500">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredRecruiters.map((rec) => (
              <>
                <tr
                  key={rec.id}
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => loadDetails(rec.id)}
                >
                  <td
                    className="px-3 py-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(rec.user_id)}
                      onChange={() => toggleSelect(rec.user_id)}
                      className="rounded border-slate-300"
                    />
                  </td>
                  <td className="px-3 py-2 text-sm font-medium text-slate-900">
                    {rec.company_name}
                    {rec.company_type && (
                      <span className="ml-1 text-xs text-slate-400">
                        ({rec.company_type})
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    {rec.email || "\u2014"}
                  </td>
                  <td
                    className="px-3 py-2"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOverrideTarget(rec);
                      setOverrideTier(rec.subscription_tier);
                      setOverrideBillingExempt(rec.billing_exempt);
                    }}
                  >
                    <TierBadge tier={rec.subscription_tier} />
                    {rec.billing_exempt && (
                      <span className="ml-1 rounded-full border border-violet-200 bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700">
                        exempt
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    {rec.seats_used}/{rec.seats_purchased}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    {rec.pipeline_count} / {rec.jobs_count} / {rec.clients_count}
                  </td>
                  <td className="px-3 py-2 text-sm">
                    {rec.is_trial_active ? (
                      <span className="rounded-full border border-amber-200 bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                        Trial ({rec.trial_days_remaining}d)
                      </span>
                    ) : (
                      <span className="text-slate-400">\u2014</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-500">
                    {formatDate(rec.created_at)}
                  </td>
                </tr>

                {/* Expanded row: jobs + clients */}
                {expandedId === rec.id && (
                  <tr key={`${rec.id}-details`}>
                    <td colSpan={8} className="bg-slate-50 px-6 py-4">
                      {detailLoading ? (
                        <p className="text-sm text-slate-500">Loading...</p>
                      ) : (
                        <div className="grid grid-cols-2 gap-6">
                          {/* Jobs */}
                          <div>
                            <h4 className="mb-2 text-sm font-semibold text-slate-700">
                              Jobs ({expandedJobs.length})
                            </h4>
                            {expandedJobs.length === 0 ? (
                              <p className="text-sm text-slate-500">
                                No jobs found.
                              </p>
                            ) : (
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="text-left text-xs font-medium uppercase text-slate-400">
                                    <th className="pb-1 pr-3">Title</th>
                                    <th className="pb-1 pr-3">Status</th>
                                    <th className="pb-1 pr-3">Client</th>
                                    <th className="pb-1 pr-3">Filled</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {expandedJobs.map((j) => (
                                    <tr
                                      key={j.id}
                                      className="border-t border-slate-100"
                                    >
                                      <td className="py-1 pr-3 font-medium">
                                        {j.title}
                                      </td>
                                      <td className="py-1 pr-3">{j.status}</td>
                                      <td className="py-1 pr-3">
                                        {j.client_company_name || "\u2014"}
                                      </td>
                                      <td className="py-1 pr-3">
                                        {j.positions_filled}/
                                        {j.positions_to_fill}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>

                          {/* Clients */}
                          <div>
                            <h4 className="mb-2 text-sm font-semibold text-slate-700">
                              Clients ({expandedClients.length})
                            </h4>
                            {expandedClients.length === 0 ? (
                              <p className="text-sm text-slate-500">
                                No clients found.
                              </p>
                            ) : (
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="text-left text-xs font-medium uppercase text-slate-400">
                                    <th className="pb-1 pr-3">Company</th>
                                    <th className="pb-1 pr-3">Status</th>
                                    <th className="pb-1 pr-3">Fee</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {expandedClients.map((c) => (
                                    <tr
                                      key={c.id}
                                      className="border-t border-slate-100"
                                    >
                                      <td className="py-1 pr-3 font-medium">
                                        {c.company_name}
                                      </td>
                                      <td className="py-1 pr-3">{c.status}</td>
                                      <td className="py-1 pr-3">
                                        {c.fee_percentage
                                          ? `${c.fee_percentage}%`
                                          : "\u2014"}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
            {filteredRecruiters.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="px-3 py-8 text-center text-sm text-slate-500"
                >
                  {searchTerm
                    ? "No recruiters match your search."
                    : "No recruiters found."}
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
                <option value="trial">Trial</option>
                <option value="solo">Solo</option>
                <option value="team">Team</option>
                <option value="agency">Agency</option>
              </select>
            </div>
            <div className="mb-4 flex items-center gap-2">
              <input
                type="checkbox"
                id="billing-exempt"
                checked={overrideBillingExempt}
                onChange={(e) => setOverrideBillingExempt(e.target.checked)}
                className="rounded border-slate-300"
              />
              <label
                htmlFor="billing-exempt"
                className="text-sm font-medium text-slate-700"
              >
                Billing exempt (immune to Stripe webhook changes)
              </label>
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
