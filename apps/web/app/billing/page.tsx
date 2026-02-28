"use client";

import { Suspense, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { fetchAuthMe, type AuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type BillingStatus = {
  plan_tier: string;
  billing_cycle: string | null;
  subscription_status: string | null;
  match_refreshes_used: number;
  match_refreshes_limit: number | null;
  tailor_requests_used: number;
  tailor_requests_limit: number | null;
};

/* ---------- Reusable components ---------- */

function UsageMeter({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  const isUnlimited = limit === null;
  const pct = isUnlimited
    ? 0
    : limit > 0
      ? Math.min((used / limit) * 100, 100)
      : 0;
  const atLimit = !isUnlimited && limit !== null && used >= limit;

  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className={atLimit ? "font-semibold text-red-600" : "text-slate-500"}>
          {used} / {isUnlimited ? "Unlimited" : limit}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all ${
            isUnlimited
              ? "w-full bg-blue-500"
              : atLimit
                ? "bg-red-500"
                : pct > 70
                  ? "bg-amber-500"
                  : "bg-blue-500"
          }`}
          style={!isUnlimited ? { width: `${pct}%` } : undefined}
        />
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const colors: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    trialing: "bg-blue-100 text-blue-800",
    past_due: "bg-amber-100 text-amber-800",
    canceled: "bg-slate-100 text-slate-600",
  };
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${
        colors[status] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function SubscriptionStateBanner({
  status,
  onPortalClick,
  portalLoading,
}: {
  status: string | null;
  onPortalClick: () => void;
  portalLoading: boolean;
}) {
  if (status === "past_due") {
    return (
      <div className="mb-6 flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <svg className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <div>
            <p className="font-medium text-amber-800">Your payment method needs attention</p>
            <p className="mt-1 text-sm text-amber-700">
              Please update your payment method to avoid service interruption.
            </p>
          </div>
        </div>
        <button
          onClick={onPortalClick}
          disabled={portalLoading}
          className="shrink-0 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
        >
          {portalLoading ? "Opening..." : "Update Payment"}
        </button>
      </div>
    );
  }

  if (status === "canceled") {
    return (
      <div className="mb-6 flex flex-col gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <svg className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="font-medium text-blue-800">Your subscription has been canceled</p>
            <p className="mt-1 text-sm text-blue-700">
              Your Pro access continues until the end of your current billing period, then reverts to Free.
            </p>
          </div>
        </div>
        <button
          onClick={onPortalClick}
          disabled={portalLoading}
          className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {portalLoading ? "Opening..." : "Reactivate"}
        </button>
      </div>
    );
  }

  if (status === "trialing") {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 p-4">
        <svg className="mt-0.5 h-5 w-5 shrink-0 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <p className="font-medium text-green-800">You&apos;re on a free trial of Pro</p>
          <p className="mt-1 text-sm text-green-700">
            Enjoy unlimited access during your trial period.
          </p>
        </div>
      </div>
    );
  }

  return null;
}

const FEATURES = [
  { name: "Job Sources", free: "Job boards", pro: "All sources (boards + direct hire + recruiter)" },
  { name: "Match Refreshes", free: "10/month", pro: "Unlimited" },
  { name: "Tailored Documents", free: "3/month", pro: "Unlimited" },
  { name: "Cover Letter Generation", free: false, pro: true },
  { name: "Interview Probability Score\u2122", free: true, pro: true },
  { name: "Priority Support", free: false, pro: true },
];

function FeatureComparisonTable() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Compare Plans</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="px-6 py-3 text-left font-medium text-slate-600">Feature</th>
              <th className="px-6 py-3 text-center font-medium text-slate-600">Free</th>
              <th className="px-6 py-3 text-center font-medium text-blue-700">Pro</th>
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((f, i) => (
              <tr key={f.name} className={i < FEATURES.length - 1 ? "border-b border-slate-50" : ""}>
                <td className={`px-6 py-3 text-slate-700 ${String(f.name).includes("\u2122") ? "font-bold" : "font-medium"}`}>{f.name}</td>
                <td className="px-6 py-3 text-center text-slate-600">
                  {typeof f.free === "string" ? (
                    f.free
                  ) : f.free ? (
                    <svg className="mx-auto h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <span className="text-slate-300">&mdash;</span>
                  )}
                </td>
                <td className="px-6 py-3 text-center font-medium text-slate-900">
                  {typeof f.pro === "string" ? (
                    f.pro
                  ) : f.pro ? (
                    <svg className="mx-auto h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <span className="text-slate-300">&mdash;</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const FAQ_ITEMS = [
  {
    q: "Can I switch between monthly and annual billing?",
    a: "Yes. Open the billing portal and you can change your plan at any time. If you switch from monthly to annual, the prorated difference is applied automatically.",
  },
  {
    q: "What happens if I cancel my subscription?",
    a: "You\u2019ll keep Pro access until the end of your current billing period, then your account reverts to the Free plan. No data is deleted.",
  },
  {
    q: "How do usage limits reset?",
    a: "Free-tier limits (match refreshes and tailored documents) reset on the 1st of each calendar month.",
  },
  {
    q: "What payment methods do you accept?",
    a: "We accept all major credit and debit cards (Visa, Mastercard, Amex, Discover) through Stripe. Payments are processed securely and we never store your card details.",
  },
];

function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Frequently Asked Questions</h2>
      </div>
      <div className="divide-y divide-slate-100">
        {FAQ_ITEMS.map((item, i) => {
          const isOpen = openIndex === i;
          return (
            <button
              key={i}
              type="button"
              onClick={() => setOpenIndex(isOpen ? null : i)}
              className="flex w-full items-start gap-3 px-6 py-4 text-left transition-colors hover:bg-slate-50"
            >
              <svg
                className={`mt-0.5 h-5 w-5 shrink-0 text-slate-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <div>
                <p className="font-medium text-slate-800">{item.q}</p>
                {isOpen && (
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.a}</p>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- Main page ---------- */

function BillingPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [me, setMe] = useState<AuthMe | null>(null);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);

  const success = searchParams.get("success") === "true";
  const canceled = searchParams.get("canceled") === "true";

  useEffect(() => {
    const init = async () => {
      const authMe = await fetchAuthMe();
      if (!authMe) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/login", redirectValue));
        return;
      }
      setMe(authMe);

      try {
        const res = await fetch(`${API_BASE}/api/billing/status`, {
          credentials: "include",
        });
        if (res.ok) {
          setBilling(await res.json());
        } else {
          setBillingError(
            "Billing is not available yet. Please contact support."
          );
        }
      } catch {
        setBillingError(
          "Billing is not available yet. Please contact support."
        );
      }
      setLoading(false);
    };
    void init();
  }, [pathname, router, searchParams]);

  const handleCheckout = async (cycle: "monthly" | "annual") => {
    setCheckoutLoading(cycle);
    setCheckoutError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/billing/checkout?billing_cycle=${cycle}`,
        { method: "POST", credentials: "include" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setCheckoutError(
          data?.detail || "Failed to create checkout session. Please try again."
        );
        return;
      }
      const data = await res.json();
      window.location.href = data.checkout_url;
    } catch {
      setCheckoutError(
        "Unable to connect to billing service. Please check your connection and try again."
      );
    } finally {
      setCheckoutLoading(null);
    }
  };

  const handlePortal = async () => {
    setPortalLoading(true);
    setPortalError(null);
    try {
      const res = await fetch(`${API_BASE}/api/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setPortalError(
          data?.detail || "Failed to open billing portal. Please try again."
        );
        return;
      }
      const data = await res.json();
      window.location.href = data.portal_url;
    } catch {
      setPortalError(
        "Unable to connect to billing service. Please check your connection and try again."
      );
    } finally {
      setPortalLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-slate-500">Loading billing...</p>
      </div>
    );
  }

  const isPro = billing?.plan_tier === "pro";

  return (
    <CandidateLayout>
      <CollapsibleTip title="Subscription Plans" defaultOpen={false}>
        <p>
          Upgrade for more match visibility, tailoring requests, Sieve AI
          messages, and career intelligence features.
        </p>
      </CollapsibleTip>

      <div className="mt-6">
        {/* Back link */}
        <a
          href="/dashboard"
          className="mb-6 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Dashboard
        </a>

        {/* Header */}
        <h1 className="text-3xl font-bold text-slate-900">Billing</h1>
        <p className="mt-1 text-slate-500">
          Manage your subscription and view usage.
        </p>

        {/* Billing error */}
        {billingError && (
          <div className="mt-6 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
            {billingError}
          </div>
        )}

        {/* Success / Canceled banners */}
        {success && (
          <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800">
            Your subscription is active! Welcome to Pro.
          </div>
        )}
        {canceled && (
          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            Checkout was canceled. No changes were made to your plan.
          </div>
        )}

        {/* Subscription state banner */}
        {billing && (
          <div className="mt-6">
            <SubscriptionStateBanner
              status={billing.subscription_status}
              onPortalClick={handlePortal}
              portalLoading={portalLoading}
            />
          </div>
        )}

        {/* Current Plan card */}
        {billing && (
          <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold text-slate-900">
                    {isPro ? "Pro Plan" : "Free Plan"}
                  </h2>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      isPro
                        ? "bg-blue-100 text-blue-800"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {isPro ? "Pro" : "Free"}
                  </span>
                </div>
                {isPro && billing.billing_cycle && (
                  <p className="mt-1 flex items-center gap-2 text-sm text-slate-500">
                    {billing.billing_cycle === "annual"
                      ? "$290/year"
                      : "$29/month"}
                    <StatusBadge status={billing.subscription_status} />
                  </p>
                )}
                {!isPro && (
                  <p className="mt-1 text-sm text-slate-500">
                    Limited usage per month
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-4 border-t border-slate-100 pt-4">
              <h3 className="text-sm font-medium text-slate-700">
                Monthly Usage
              </h3>
              <UsageMeter
                label="Match Refreshes"
                used={billing.match_refreshes_used}
                limit={billing.match_refreshes_limit}
              />
              <UsageMeter
                label="Tailored Documents"
                used={billing.tailor_requests_used}
                limit={billing.tailor_requests_limit}
              />
            </div>
          </div>
        )}

        {/* Feature comparison table */}
        <div className="mt-6">
          <FeatureComparisonTable />
        </div>

        {/* Upgrade section (free users) */}
        {!isPro && (
          <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-900">
              Upgrade to Pro
            </h2>
            <p className="mt-1 text-slate-500">
              Unlimited match refreshes, all job sources, tailored documents, and cover letter generation.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <button
                onClick={() => handleCheckout("monthly")}
                disabled={checkoutLoading !== null}
                className="w-full rounded-lg bg-blue-600 px-4 py-3 font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {checkoutLoading === "monthly"
                  ? "Redirecting..."
                  : "Monthly \u2014 $29/mo"}
              </button>
              <button
                onClick={() => handleCheckout("annual")}
                disabled={checkoutLoading !== null}
                className="w-full rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 font-medium text-blue-700 transition hover:bg-blue-100 disabled:opacity-50"
              >
                {checkoutLoading === "annual"
                  ? "Redirecting..."
                  : "Annual \u2014 $290/yr (save 17%)"}
              </button>
            </div>

            {checkoutError && (
              <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                {checkoutError}
              </div>
            )}
          </div>
        )}

        {/* Manage subscription (pro users) */}
        {isPro && (
          <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">
              Manage Subscription
            </h2>
            <p className="mt-1 text-slate-500">
              Update payment method, change plan, or cancel.
            </p>
            <button
              onClick={handlePortal}
              disabled={portalLoading}
              className="mt-4 rounded-lg bg-slate-100 px-5 py-2.5 font-medium text-slate-700 transition hover:bg-slate-200 disabled:opacity-50"
            >
              {portalLoading ? "Redirecting..." : "Open Billing Portal"}
            </button>

            {portalError && (
              <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                {portalError}
              </div>
            )}
          </div>
        )}

        {/* FAQ */}
        <div className="mt-6">
          <FAQSection />
        </div>
      </div>
    </CandidateLayout>
  );
}

export default function BillingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50">
          <p className="text-slate-500">Loading...</p>
        </div>
      }
    >
      <BillingPageContent />
    </Suspense>
  );
}
