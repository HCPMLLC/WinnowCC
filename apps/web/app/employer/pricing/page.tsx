"use client";

import Link from "next/link";

const TIERS = [
  {
    name: "Free",
    price: "$0",
    interval: "/mo",
    description: "Try Winnow with a single posting",
    features: [
      "1 active job posting",
      "5 candidate views per month",
      "1 AI job parse per month",
      "Google Jobs distribution",
    ],
    cta: "Get Started",
    href: "/login?mode=signup&role=employer",
    highlight: false,
  },
  {
    name: "Starter",
    price: "$49",
    interval: "/mo",
    annual: "$399/year (save 32%)",
    description: "For growing companies",
    features: [
      "5 active job postings",
      "50 candidate views per month",
      "10 AI job parses per month",
      "Google Jobs, Indeed & ZipRecruiter",
      "Basic cross-board analytics",
      "Basic bias detection",
    ],
    cta: "Get Started",
    href: "/login?mode=signup&role=employer",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$149",
    interval: "/mo",
    annual: "$1,199/year (save 33%)",
    description: "For hiring teams",
    features: [
      "25 active job postings",
      "200 candidate views per month",
      "Unlimited AI job parsing",
      "All job board distribution",
      "Full cross-board analytics",
      "Salary intelligence",
      "Full bias detection",
    ],
    cta: "Get Started",
    href: "/login?mode=signup&role=employer",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    interval: "",
    description: "For large organizations",
    features: [
      "Unlimited job postings",
      "Unlimited candidate views",
      "Unlimited AI job parsing",
      "All job board distribution",
      "Full analytics & intelligence",
      "Dedicated account manager",
      "Custom integrations",
    ],
    cta: "Contact Sales",
    href: "mailto:sales@winnow.careers",
    highlight: false,
  },
];

export default function EmployerPricingPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-amber-600">
            Employer Plans
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Find candidates who actually fit
          </h1>
          <p className="mt-4 text-lg text-slate-600">
            AI-powered matching, multi-board distribution, and bias detection.
          </p>
        </div>

        <div className="mx-auto mt-16 grid max-w-5xl gap-8 lg:grid-cols-4">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`relative rounded-2xl bg-white p-8 ${
                tier.highlight
                  ? "border-2 border-amber-500 shadow-lg"
                  : "border border-slate-200"
              }`}
            >
              {tier.highlight && (
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
              <Link
                href={tier.href}
                className={`mt-8 block rounded-xl py-2.5 text-center text-sm font-semibold transition-colors ${
                  tier.highlight
                    ? "bg-amber-500 text-slate-900 hover:bg-amber-400"
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center">
          <Link
            href="/"
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            &larr; Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
