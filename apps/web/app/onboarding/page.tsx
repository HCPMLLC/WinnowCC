"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { normalizeRedirect, withRedirectParam } from "../lib/redirects";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type OnboardingStatus = {
  completed: boolean;
  current_step: string;
  missing: string[];
};

type LocationEntry = {
  city: string;
  state: string;
  country: string;
  radius_miles: number;
};

function OnboardingPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect");
  const redirectTarget = normalizeRedirect(redirectParam, "/matches");

  // UI state
  const [step, setStep] = useState<"loading" | "preferences" | "consent">("loading");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Preferences state
  const [roles, setRoles] = useState("");
  const [locationCity, setLocationCity] = useState("");
  const [locationState, setLocationState] = useState("");
  const [locationCountry, setLocationCountry] = useState("US");
  const [workMode, setWorkMode] = useState("any");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [employmentTypes, setEmploymentTypes] = useState<string[]>(["full_time"]);
  const [travelPercent, setTravelPercent] = useState("");

  // Consent state
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [mjassConsent, setMjassConsent] = useState(false);
  const [dataProcessingConsent, setDataProcessingConsent] = useState(false);
  const [applicationMode, setApplicationMode] = useState<"review_required" | "auto_apply_limited">("review_required");

  useEffect(() => {
    const checkStatus = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        router.replace(withRedirectParam("/login", "/onboarding"));
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/api/onboarding/status`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to check onboarding status");
        }
        const status = (await response.json()) as OnboardingStatus;

        if (status.completed) {
          router.replace(redirectTarget);
          return;
        }

        if (status.missing.includes("preferences")) {
          setStep("preferences");
        } else if (status.missing.includes("consent")) {
          setStep("consent");
        } else {
          setStep("preferences");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load status");
        setStep("preferences");
      }
    };
    void checkStatus();
  }, [redirectTarget, router]);

  const toggleEmploymentType = (type: string) => {
    setEmploymentTypes((current) =>
      current.includes(type)
        ? current.filter((t) => t !== type)
        : [...current, type]
    );
  };

  const handlePreferencesSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const rolesList = roles
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean);

    if (rolesList.length === 0) {
      setError("Please enter at least one target role");
      setIsSubmitting(false);
      return;
    }

    const locations: LocationEntry[] = [
      {
        city: locationCity || "Any",
        state: locationState || "",
        country: locationCountry || "US",
        radius_miles: 50,
      },
    ];

    try {
      const response = await fetch(`${API_BASE}/api/onboarding/preferences`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          roles: rolesList,
          locations,
          work_mode: workMode,
          salary_min: salaryMin ? Number(salaryMin) : null,
          salary_max: salaryMax ? Number(salaryMax) : null,
          salary_currency: "USD",
          employment_types: employmentTypes,
          travel_percent_max: travelPercent ? Number(travelPercent) : null,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to save preferences");
      }

      setStep("consent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConsentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    if (!acceptTerms || !mjassConsent || !dataProcessingConsent) {
      setError("All consents are required to continue");
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/onboarding/consent`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          terms_version: "2026-01-31-v1",
          accept_terms: true,
          mjass_consent: true,
          data_processing_consent: true,
          application_mode: applicationMode,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to save consent");
      }

      router.push(redirectTarget);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save consent");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (step === "loading") {
    return (
      <main className="mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center px-6 py-16">
        <p className="text-sm text-slate-600">Loading...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">
          {step === "preferences" ? "Job Preferences" : "Consent & Application Mode"}
        </h1>
        <p className="text-sm text-slate-600">
          {step === "preferences"
            ? "Tell us what you're looking for so we can find the best matches."
            : "Review and accept to enable MJASS job matching."}
        </p>
        <div className="mt-2 flex gap-2">
          <div
            className={`h-2 w-24 rounded-full ${
              step === "preferences" ? "bg-slate-900" : "bg-slate-300"
            }`}
          />
          <div
            className={`h-2 w-24 rounded-full ${
              step === "consent" ? "bg-slate-900" : "bg-slate-300"
            }`}
          />
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {step === "preferences" && (
        <form
          onSubmit={handlePreferencesSubmit}
          className="flex flex-col gap-5 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Target Roles (comma-separated) *
            <input
              type="text"
              value={roles}
              onChange={(e) => setRoles(e.target.value)}
              placeholder="Software Engineer, DevOps Engineer, SRE"
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              required
            />
          </label>

          <div className="grid gap-4 md:grid-cols-3">
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              City
              <input
                type="text"
                value={locationCity}
                onChange={(e) => setLocationCity(e.target.value)}
                placeholder="Chicago"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              State
              <input
                type="text"
                value={locationState}
                onChange={(e) => setLocationState(e.target.value)}
                placeholder="IL"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              Country
              <input
                type="text"
                value={locationCountry}
                onChange={(e) => setLocationCountry(e.target.value)}
                placeholder="US"
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
          </div>

          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Work Mode
            <select
              value={workMode}
              onChange={(e) => setWorkMode(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="any">Any (Remote, Hybrid, or On-site)</option>
              <option value="remote">Remote Only</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site Only</option>
            </select>
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              Minimum Salary (USD)
              <input
                type="number"
                value={salaryMin}
                onChange={(e) => setSalaryMin(e.target.value)}
                placeholder="100000"
                min={0}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              Maximum Salary (USD)
              <input
                type="number"
                value={salaryMax}
                onChange={(e) => setSalaryMax(e.target.value)}
                placeholder="180000"
                min={0}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
          </div>

          <div className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Employment Type *
            <div className="flex flex-wrap gap-4">
              {["full_time", "part_time", "contract", "internship"].map((type) => (
                <label key={type} className="flex items-center gap-2 font-normal">
                  <input
                    type="checkbox"
                    checked={employmentTypes.includes(type)}
                    onChange={() => toggleEmploymentType(type)}
                  />
                  {type.replace("_", "-")}
                </label>
              ))}
            </div>
          </div>

          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Max Travel (% of time)
            <input
              type="number"
              value={travelPercent}
              onChange={(e) => setTravelPercent(e.target.value)}
              placeholder="10"
              min={0}
              max={100}
              className="w-32 rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-fit rounded-full bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-500"
          >
            {isSubmitting ? "Saving..." : "Continue"}
          </button>
        </form>
      )}

      {step === "consent" && (
        <form
          onSubmit={handleConsentSubmit}
          className="flex flex-col gap-5 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          <section className="rounded-2xl border border-blue-100 bg-blue-50 p-6">
            <h2 className="text-lg font-semibold text-slate-900">
              MJASS - Matched Jobs & Application Staging
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              MJASS analyzes your resume against job listings to find the best matches,
              explains why each job is a good fit, and helps you prepare tailored
              application materials.
            </p>
            <ul className="mt-4 list-inside list-disc text-sm text-slate-600">
              <li>AI-powered job matching with explainability</li>
              <li>Tailored resume and cover letter generation</li>
              <li>Application draft review before submission</li>
              <li>Full audit trail of your decisions</li>
            </ul>
          </section>

          <div className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Application Mode
            <p className="font-normal text-slate-500">
              Choose how you want to review matched jobs before applying.
            </p>
            <div className="mt-2 flex flex-col gap-3">
              <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4 hover:bg-slate-50">
                <input
                  type="radio"
                  name="applicationMode"
                  value="review_required"
                  checked={applicationMode === "review_required"}
                  onChange={() => setApplicationMode("review_required")}
                  className="mt-1"
                />
                <div>
                  <div className="font-semibold">Review Required (Recommended)</div>
                  <p className="font-normal text-slate-500">
                    You manually approve each application draft before any action is taken.
                  </p>
                </div>
              </label>
              <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4 hover:bg-slate-50">
                <input
                  type="radio"
                  name="applicationMode"
                  value="auto_apply_limited"
                  checked={applicationMode === "auto_apply_limited"}
                  onChange={() => setApplicationMode("auto_apply_limited")}
                  className="mt-1"
                />
                <div>
                  <div className="font-semibold">Auto-Apply (Limited)</div>
                  <p className="font-normal text-slate-500">
                    Low-friction applications may be submitted automatically for high-confidence matches.
                  </p>
                </div>
              </label>
            </div>
          </div>

          <section className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
            <h2 className="text-lg font-semibold text-slate-900">Consents</h2>
            <div className="mt-4 flex flex-col gap-3 text-sm text-slate-700">
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={acceptTerms}
                  onChange={(e) => setAcceptTerms(e.target.checked)}
                  className="mt-1"
                  required
                />
                <span>
                  I accept the <span className="font-semibold">Terms of Service</span> and{" "}
                  <span className="font-semibold">Privacy Policy</span>. *
                </span>
              </label>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={dataProcessingConsent}
                  onChange={(e) => setDataProcessingConsent(e.target.checked)}
                  className="mt-1"
                  required
                />
                <span>
                  I consent to processing my resume and profile data for job matching. *
                </span>
              </label>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={mjassConsent}
                  onChange={(e) => setMjassConsent(e.target.checked)}
                  className="mt-1"
                  required
                />
                <span>
                  I consent to MJASS creating application drafts and tracking my decisions. *
                </span>
              </label>
            </div>
          </section>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep("preferences")}
              className="rounded-full border border-slate-300 px-6 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Back
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !acceptTerms || !mjassConsent || !dataProcessingConsent}
              className="rounded-full bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-500"
            >
              {isSubmitting ? "Completing..." : "Complete Setup"}
            </button>
          </div>
        </form>
      )}
    </main>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense>
      <OnboardingPageContent />
    </Suspense>
  );
}
