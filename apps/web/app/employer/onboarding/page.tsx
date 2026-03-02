"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ProgressRing } from "../../components/ProgressRing";
import { parseApiError } from "../../lib/api-error";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const COMPANY_SIZES = [
  "1-10",
  "11-50",
  "51-200",
  "201-500",
  "501-1000",
  "1000+",
];

const INDUSTRIES = [
  "Aerospace & Defense",
  "Agriculture",
  "Automotive",
  "Construction",
  "Consulting",
  "Consumer Goods",
  "Education",
  "Energy & Utilities",
  "Entertainment & Media",
  "Financial Services",
  "Food & Beverage",
  "Government",
  "Healthcare",
  "Hospitality & Tourism",
  "Insurance",
  "Legal",
  "Logistics & Transportation",
  "Manufacturing",
  "Mining & Metals",
  "Nonprofit",
  "Pharmaceuticals",
  "Professional Services",
  "Real Estate",
  "Retail & E-Commerce",
  "Technology",
  "Telecommunications",
  "Other",
];

export default function EmployerOnboarding() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    company_name: "",
    company_size: "",
    industry: "",
    company_website: "",
    company_description: "",
    contact_first_name: "",
    contact_last_name: "",
    contact_email: "",
    contact_phone: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const completionPercent = useMemo(() => {
    let pct = 0;
    // Required fields (15% each)
    if (formData.company_name.trim()) pct += 15;
    if (formData.contact_first_name.trim()) pct += 15;
    if (formData.contact_last_name.trim()) pct += 15;
    if (formData.contact_email.trim()) pct += 15;
    if (formData.company_size) pct += 15;
    if (formData.company_website.trim()) pct += 15;
    // Optional fields (~3-4% each, totaling 10%)
    if (formData.industry) pct += 3;
    if (formData.contact_phone.trim()) pct += 3;
    if (formData.company_description.trim()) pct += 4;
    return pct;
  }, [formData]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/employer/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(parseApiError(data, "Failed to create profile"));
      }

      router.push("/employer/dashboard");
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
          Let&apos;s set up your employer profile to get started.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Name *
            </label>
            <input
              type="text"
              required
              value={formData.company_name}
              onChange={(e) =>
                setFormData({ ...formData, company_name: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="Acme Corp"
            />
          </div>

          {/* Primary Contact */}
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">
              Primary Contact
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  First Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.contact_first_name}
                  onChange={(e) =>
                    setFormData({ ...formData, contact_first_name: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="Jane"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Last Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.contact_last_name}
                  onChange={(e) =>
                    setFormData({ ...formData, contact_last_name: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="Smith"
                />
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Email *
                </label>
                <input
                  type="email"
                  required
                  value={formData.contact_email}
                  onChange={(e) =>
                    setFormData({ ...formData, contact_email: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="jane@acme.com"
                />
                <p className="mt-1 text-xs text-slate-500">
                  Must match your company website domain
                </p>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={formData.contact_phone}
                  onChange={(e) =>
                    setFormData({ ...formData, contact_phone: e.target.value })
                  }
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="(555) 123-4567"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Size *
            </label>
            <select
              required
              value={formData.company_size}
              onChange={(e) =>
                setFormData({ ...formData, company_size: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            >
              <option value="">Select size...</option>
              {COMPANY_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size} employees
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Industry
            </label>
            <select
              value={formData.industry}
              onChange={(e) =>
                setFormData({ ...formData, industry: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            >
              <option value="">Select industry...</option>
              {INDUSTRIES.map((ind) => (
                <option key={ind} value={ind}>
                  {ind}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Website *
            </label>
            <input
              type="url"
              required
              value={formData.company_website}
              onChange={(e) =>
                setFormData({ ...formData, company_website: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="https://acme.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Description
            </label>
            <textarea
              value={formData.company_description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  company_description: e.target.value,
                })
              }
              rows={4}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="Tell candidates about your company..."
            />
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
            {isLoading ? "Creating profile..." : "Complete Setup"}
          </button>
        </form>
      </div>
    </div>
  );
}
