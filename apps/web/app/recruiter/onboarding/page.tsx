"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ProgressRing } from "../../components/ProgressRing";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const COMPANY_TYPES = [
  { value: "agency", label: "Staffing Agency" },
  { value: "boutique", label: "Boutique Firm" },
  { value: "corporate", label: "Corporate Recruiting" },
  { value: "independent", label: "Independent Recruiter" },
];

export default function RecruiterOnboarding() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    company_name: "",
    company_type: "",
    company_website: "",
    specializations: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const completionPercent = useMemo(() => {
    let pct = 0;
    if (formData.company_name.trim()) pct += 40;
    if (formData.company_type) pct += 20;
    if (formData.company_website.trim()) pct += 20;
    if (formData.specializations.trim()) pct += 20;
    return pct;
  }, [formData]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const payload = {
        company_name: formData.company_name,
        company_type: formData.company_type || null,
        company_website: formData.company_website || null,
        specializations: formData.specializations
          ? formData.specializations.split(",").map((s) => s.trim()).filter(Boolean)
          : null,
      };

      const res = await fetch(`${API_BASE}/api/recruiter/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create profile");
      }

      router.push("/recruiter/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold text-slate-900">
            Welcome to Winnow!
          </h1>
          <ProgressRing percent={completionPercent} />
        </div>
        <p className="mt-2 text-slate-600">
          Set up your recruiter profile to start sourcing candidates. Your
          14-day free trial begins when you complete this form.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company / Agency Name *
            </label>
            <input
              type="text"
              required
              value={formData.company_name}
              onChange={(e) =>
                setFormData({ ...formData, company_name: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="Acme Staffing"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Type
            </label>
            <select
              value={formData.company_type}
              onChange={(e) =>
                setFormData({ ...formData, company_type: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            >
              <option value="">Select type...</option>
              {COMPANY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Website
            </label>
            <input
              type="url"
              value={formData.company_website}
              onChange={(e) =>
                setFormData({ ...formData, company_website: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="https://acmestaffing.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Specializations
            </label>
            <input
              type="text"
              value={formData.specializations}
              onChange={(e) =>
                setFormData({ ...formData, specializations: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="Engineering, Product, Data Science (comma-separated)"
            />
            <p className="mt-1 text-xs text-slate-400">
              Separate multiple specializations with commas
            </p>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-slate-900 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isLoading ? "Creating profile..." : "Start Free Trial"}
          </button>
        </form>
      </div>
    </div>
  );
}
