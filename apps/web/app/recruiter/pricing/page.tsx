"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const TIER_ORDER = ["trial", "solo", "team", "agency"];

const TIERS = [
  {
    key: "trial",
    name: "14-Day Free Trial",
    price: "$0",
    interval: "",
    description: "Full access for 14 days",
    features: [
      "1 seat",
      "Unlimited candidate briefs",
      "Chrome extension",
      "Unlimited salary lookups",
      "Full migration toolkit",
      "Full client CRM",
    ],
    highlight: false,
  },
  {
    key: "solo",
    name: "Solo",
    price: "$39",
    interval: "/mo",
    annual: "$349/year (save 25%)",
    description: "For independent recruiters",
    features: [
      "1 seat",
      "20 candidate briefs per month",
      "Chrome extension",
      "5 salary lookups per month",
      "Full migration toolkit",
      "Basic client CRM",
      "Jobs visible to Pro candidates",
    ],
    highlight: false,
  },
  {
    key: "team",
    name: "Team",
    price: "$89",
    interval: "/user/mo",
    annual: "$799/user/year (save 25%)",
    description: "For recruiting teams",
    features: [
      "Up to 10 seats",
      "100 candidate briefs per month",
      "Chrome extension",
      "50 salary lookups per month",
      "Full migration toolkit",
      "Full client CRM",
      "Jobs visible to Pro candidates",
    ],
    highlight: true,
  },
  {
    key: "agency",
    name: "Agency",
    price: "$129",
    interval: "/user/mo",
    annual: "$1,159/user/year (save 25%)",
    description: "For staffing agencies",
    features: [
      "Unlimited seats",
      "500 candidate briefs per month",
      "Chrome extension",
      "Unlimited salary lookups",
      "Full migration toolkit",
      "Full client CRM",
      "Jobs visible to Pro candidates",
    ],
    highlight: false,
  },
];

export default function RecruiterPricingPage() {
  const [currentTier, setCurrentTier] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/recruiter/profile`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.subscription_tier) {
          setCurrentTier(data.subscription_tier);
          setIsLoggedIn(true);
        }
      })
      .catch(() => {});
  }, []);

  async function handleUpgrade(tierKey: string) {
    setUpgrading(tierKey);
    try {
      const res = await fetch(`${API_BASE}/api/billing/unified-checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          segment: "recruiter",
          tier: tierKey,
          interval: "monthly",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Unable to start checkout. Please try again.");
        return;
      }
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch {
      alert("Something went wrong. Please try again.");
    } finally {
      setUpgrading(null);
    }
  }

  function getCtaForTier(tierKey: string) {
    if (!isLoggedIn) {
      if (tierKey === "agency") return { label: "Contact Sales", action: "mailto" };
      if (tierKey === "trial") return { label: "Start Free Trial", action: "signup" };
      return { label: "Get Started", action: "signup" };
    }

    const currentIdx = TIER_ORDER.indexOf(currentTier || "trial");
    const tierIdx = TIER_ORDER.indexOf(tierKey);

    if (tierKey === currentTier) return { label: "Current Plan", action: "none" };
    if (tierIdx < currentIdx) return { label: "Current Plan Includes This", action: "none" };
    if (tierKey === "agency") return { label: "Contact Sales", action: "mailto" };
    return { label: "Upgrade", action: "checkout" };
  }

  return (
    <div className="space-y-8">
      <div className="text-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-amber-600">
          Recruiter Plans
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Place faster with AI-powered intel
        </h1>
        <p className="mt-4 text-lg text-slate-600">
          Candidate briefs, salary lookups, and CRM migration in one platform.
        </p>
      </div>

      <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-4">
        {TIERS.map((tier) => {
          const cta = getCtaForTier(tier.key);
          const isCurrent = isLoggedIn && tier.key === currentTier;

          return (
            <div
              key={tier.key}
              className={`relative rounded-2xl bg-white p-8 ${
                isCurrent
                  ? "border-2 border-emerald-500 shadow-lg"
                  : tier.highlight && !isLoggedIn
                    ? "border-2 border-amber-500 shadow-lg"
                    : "border border-slate-200"
              }`}
            >
              {isCurrent && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-0.5 text-xs font-semibold text-white">
                  Your Plan
                </div>
              )}
              {tier.highlight && !isLoggedIn && !isCurrent && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-500 px-3 py-0.5 text-xs font-semibold text-slate-900">
                  Popular
                </div>
              )}
              <h3 className="text-lg font-semibold text-slate-900">
                {tier.name}
              </h3>
              <p className="mt-1 text-sm text-slate-500">{tier.description}</p>
              <p className="mt-6">
                <span className="text-4xl font-bold text-slate-900">
                  {tier.price}
                </span>
                <span className="text-sm text-slate-500">{tier.interval}</span>
              </p>
              {tier.annual && (
                <p className="text-xs text-slate-400">{tier.annual}</p>
              )}
              <ul className="mt-8 space-y-3 text-sm text-slate-600">
                {tier.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-emerald-500">&#10003;</span> {f}
                  </li>
                ))}
              </ul>

              {cta.action === "none" ? (
                <span
                  className={`mt-8 block rounded-xl py-2.5 text-center text-sm font-semibold ${
                    isCurrent
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-slate-100 text-slate-400"
                  }`}
                >
                  {cta.label}
                </span>
              ) : cta.action === "mailto" ? (
                <a
                  href="mailto:sales@winnow.careers"
                  className="mt-8 block rounded-xl border border-slate-300 py-2.5 text-center text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                >
                  {cta.label}
                </a>
              ) : cta.action === "checkout" ? (
                <button
                  onClick={() => handleUpgrade(tier.key)}
                  disabled={upgrading === tier.key}
                  className={`mt-8 block w-full rounded-xl py-2.5 text-center text-sm font-semibold transition-colors ${
                    tier.highlight
                      ? "bg-amber-500 text-slate-900 hover:bg-amber-400 disabled:bg-amber-300"
                      : "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300"
                  }`}
                >
                  {upgrading === tier.key ? "Redirecting..." : cta.label}
                </button>
              ) : (
                <Link
                  href="/login?mode=signup&role=recruiter"
                  className={`mt-8 block rounded-xl py-2.5 text-center text-sm font-semibold transition-colors ${
                    tier.highlight
                      ? "bg-amber-500 text-slate-900 hover:bg-amber-400"
                      : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {cta.label}
                </Link>
              )}
            </div>
          );
        })}
      </div>

      <div className="text-center">
        <Link
          href={isLoggedIn ? "/recruiter" : "/"}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          &larr; {isLoggedIn ? "Back to dashboard" : "Back to home"}
        </Link>
      </div>
    </div>
  );
}
