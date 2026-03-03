"use client";

import { useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface CounterOffer {
  target_salary: number;
  minimum_acceptable: number;
  script: string;
  justification_points: string[];
}

interface AlternativeAsk {
  item: string;
  suggested_amount: string;
  script: string;
}

interface CoachingResult {
  offer_assessment: {
    overall: string;
    salary_position: string;
    total_comp_analysis: string;
  };
  negotiation_strategy: {
    approach: string;
    reasoning: string;
    risk_level: string;
  };
  counter_offer: CounterOffer;
  alternative_asks: AlternativeAsk[];
  red_flags: string[];
  positive_signals: string[];
  timeline_advice: string;
}

interface Props {
  matchId: number;
  jobTitle: string;
  company: string;
  onClose: () => void;
}

export default function SalaryCoachModal({
  matchId,
  jobTitle,
  company,
  onClose,
}: Props) {
  const [step, setStep] = useState<"input" | "loading" | "result">("input");
  const [salary, setSalary] = useState("");
  const [bonus, setBonus] = useState("");
  const [equity, setEquity] = useState("");
  const [result, setResult] = useState<CoachingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setStep("loading");
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/salary-coaching`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            salary: parseInt(salary.replace(/,/g, "")),
            bonus: bonus ? parseInt(bonus.replace(/,/g, "")) : null,
            equity: equity || null,
          }),
        },
      );

      if (res.status === 402) {
        setError("upgrade");
        setStep("input");
        return;
      }

      if (!res.ok) throw new Error("Failed to analyze offer");

      const data = await res.json();
      setResult(data);
      setStep("result");
    } catch {
      setError("Failed to analyze offer. Please try again.");
      setStep("input");
    }
  };

  const formatCurrency = (n: number) => `$${n.toLocaleString()}`;

  const assessmentColors: Record<string, string> = {
    below_market: "bg-red-100 text-red-800",
    at_market: "bg-yellow-100 text-yellow-800",
    above_market: "bg-green-100 text-green-800",
  };

  const riskColors: Record<string, string> = {
    low: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    high: "bg-red-100 text-red-700",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Salary Negotiation Coach
            </h2>
            <p className="text-sm text-gray-500">
              {jobTitle} at {company}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {error === "upgrade" && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="font-medium text-amber-800">Pro Feature</p>
            <p className="text-sm text-amber-700">
              Salary negotiation coaching is available on the Pro plan.
            </p>
            <a
              href="/settings/billing"
              className="text-sm text-amber-800 underline"
            >
              Upgrade to Pro
            </a>
          </div>
        )}

        {error && error !== "upgrade" && (
          <p className="mb-4 text-sm text-red-600">{error}</p>
        )}

        {step === "input" && (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Offered Base Salary *
              </label>
              <input
                type="text"
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                placeholder="120,000"
                className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Bonus (optional)
                </label>
                <input
                  type="text"
                  value={bonus}
                  onChange={(e) => setBonus(e.target.value)}
                  placeholder="15,000"
                  className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Equity (optional)
                </label>
                <input
                  type="text"
                  value={equity}
                  onChange={(e) => setEquity(e.target.value)}
                  placeholder="0.1% or 10,000 RSUs"
                  className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>
            <button
              onClick={handleSubmit}
              disabled={!salary}
              className="w-full rounded-lg bg-emerald-600 py-3 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              Analyze My Offer
            </button>
          </div>
        )}

        {step === "loading" && (
          <div className="py-12 text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent" />
            <p className="text-gray-600">Analyzing your offer...</p>
          </div>
        )}

        {step === "result" && result && (
          <div className="space-y-6">
            {/* Assessment */}
            <div
              className={`rounded-lg p-4 ${assessmentColors[result.offer_assessment.overall] || "bg-gray-100 text-gray-800"}`}
            >
              <p className="font-medium capitalize">
                {result.offer_assessment.overall.replace("_", " ")}
              </p>
              <p className="mt-1 text-sm">
                {result.offer_assessment.salary_position}
              </p>
              {result.offer_assessment.total_comp_analysis && (
                <p className="mt-1 text-sm">
                  {result.offer_assessment.total_comp_analysis}
                </p>
              )}
            </div>

            {/* Strategy */}
            <div>
              <h3 className="mb-2 font-medium text-gray-900">
                Recommended Strategy
              </h3>
              <p className="text-sm text-gray-600">
                {result.negotiation_strategy.reasoning}
              </p>
              <span
                className={`mt-2 inline-block rounded-full px-2 py-1 text-xs ${riskColors[result.negotiation_strategy.risk_level] || "bg-gray-100 text-gray-700"}`}
              >
                {result.negotiation_strategy.risk_level} risk
              </span>
            </div>

            {/* Counter Offer */}
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
              <h3 className="mb-2 font-medium text-blue-900">
                Your Counter Script
              </h3>
              <p className="text-sm italic text-blue-800">
                &ldquo;{result.counter_offer.script}&rdquo;
              </p>
              <div className="mt-3 flex gap-4 text-sm">
                <div>
                  <p className="text-blue-600">Target</p>
                  <p className="font-bold text-blue-900">
                    {formatCurrency(result.counter_offer.target_salary)}
                  </p>
                </div>
                <div>
                  <p className="text-blue-600">Minimum</p>
                  <p className="font-bold text-blue-900">
                    {formatCurrency(result.counter_offer.minimum_acceptable)}
                  </p>
                </div>
              </div>
            </div>

            {/* Justification Points */}
            {result.counter_offer.justification_points?.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium text-gray-900">
                  Your Justification Points
                </h3>
                <ul className="space-y-1 text-sm text-gray-600">
                  {result.counter_offer.justification_points.map((p, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-emerald-500">&#10003;</span> {p}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Alternative Asks */}
            {result.alternative_asks?.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium text-gray-900">
                  If Salary Is Fixed, Ask For:
                </h3>
                <div className="space-y-2">
                  {result.alternative_asks.map((ask, i) => (
                    <div
                      key={i}
                      className="rounded-lg bg-gray-50 p-3 text-sm"
                    >
                      <p className="font-medium text-gray-900">
                        {ask.item}: {ask.suggested_amount}
                      </p>
                      <p className="mt-1 text-xs text-gray-600">
                        &ldquo;{ask.script}&rdquo;
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Red Flags */}
            {result.red_flags?.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium text-red-700">Watch Out For</h3>
                <ul className="space-y-1 text-sm text-red-600">
                  {result.red_flags.map((flag, i) => (
                    <li key={i}>- {flag}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Positive Signals */}
            {result.positive_signals?.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium text-green-700">
                  Positive Signals
                </h3>
                <ul className="space-y-1 text-sm text-green-600">
                  {result.positive_signals.map((sig, i) => (
                    <li key={i}>+ {sig}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Timeline */}
            <div className="rounded-lg bg-gray-100 p-3 text-sm">
              <p className="font-medium text-gray-900">Timing</p>
              <p className="text-gray-600">{result.timeline_advice}</p>
            </div>

            <button
              onClick={onClose}
              className="w-full rounded-lg bg-gray-100 py-2 text-gray-700 hover:bg-gray-200"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
