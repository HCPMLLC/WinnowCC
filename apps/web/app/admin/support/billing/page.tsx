"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type BillingIssueUser = {
  user_id: number;
  email: string;
  segment: string;
  tier: string;
  subscription_status: string | null;
  detail: string | null;
};

type BillingData = {
  past_due: BillingIssueUser[];
  near_limits: BillingIssueUser[];
  tier_mismatches: BillingIssueUser[];
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function IssueTable({
  title,
  description,
  rows,
  borderColor,
}: {
  title: string;
  description: string;
  rows: BillingIssueUser[];
  borderColor: string;
}) {
  return (
    <div className={`rounded-2xl border bg-white p-5 ${borderColor}`}>
      <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
      <p className="mb-3 text-xs text-slate-500">{description}</p>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">None found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="pb-2 pr-3">Email</th>
                <th className="pb-2 pr-3">Segment</th>
                <th className="pb-2 pr-3">Tier</th>
                <th className="pb-2 pr-3">Status</th>
                <th className="pb-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="py-2 pr-3">
                    <Link
                      href={`/admin/support/lookup?q=${encodeURIComponent(row.email)}`}
                      className="text-blue-600 hover:underline"
                    >
                      {row.email}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium">
                      {row.segment}
                    </span>
                  </td>
                  <td className="py-2 pr-3 font-medium">{row.tier}</td>
                  <td className="py-2 pr-3">{row.subscription_status ?? "-"}</td>
                  <td className="py-2 text-slate-500">{row.detail ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function BillingDiagnosticsPage() {
  const router = useRouter();
  const [data, setData] = useState<BillingData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/admin/support/billing-issues`, {
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
        if (!res.ok) throw new Error("Failed to load billing data");
        setData(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    };
    void load();
  }, [router]);

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
      <header>
        <h1 className="text-3xl font-semibold">Billing Diagnostics</h1>
        <p className="mt-1 text-sm text-slate-600">
          Past due subscriptions, users near limits, and tier mismatches.
        </p>
      </header>

      <IssueTable
        title="Past Due"
        description="Subscriptions with past_due status across all segments."
        rows={data.past_due}
        borderColor="border-red-200"
      />

      <IssueTable
        title="Near Limits"
        description="Users at 80%+ of their daily usage limit today."
        rows={data.near_limits}
        borderColor="border-amber-200"
      />

      <IssueTable
        title="Tier Mismatches"
        description="Users with a paid tier but canceled or inactive subscription."
        rows={data.tier_mismatches}
        borderColor="border-orange-200"
      />
    </div>
  );
}
