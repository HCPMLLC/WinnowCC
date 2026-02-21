"use client";

import { useEffect, useState } from "react";

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

interface EmployerProfile {
  id: number;
  company_name: string;
  company_size: string | null;
  industry: string | null;
  company_website: string | null;
  company_description: string | null;
  company_logo_url: string | null;
  billing_email: string | null;
  subscription_tier: string;
  subscription_status: string;
}

interface SubscriptionDetails {
  tier: string;
  status: string;
  has_subscription: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export default function EmployerSettingsPage() {
  const [profile, setProfile] = useState<EmployerProfile | null>(null);
  const [subscription, setSubscription] =
    useState<SubscriptionDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    company_name: "",
    company_size: "",
    industry: "",
    company_website: "",
    company_description: "",
    billing_email: "",
  });

  useEffect(() => {
    async function fetchData() {
      try {
        const [profileRes, subRes] = await Promise.all([
          fetch(`${API_BASE}/api/employer/profile`, {
            credentials: "include",
          }),
          fetch(`${API_BASE}/api/employer/billing/subscription`, {
            credentials: "include",
          }),
        ]);

        if (profileRes.ok) {
          const data: EmployerProfile = await profileRes.json();
          setProfile(data);
          setFormData({
            company_name: data.company_name || "",
            company_size: data.company_size || "",
            industry: data.industry || "",
            company_website: data.company_website || "",
            company_description: data.company_description || "",
            billing_email: data.billing_email || "",
          });
        }

        if (subRes.ok) {
          setSubscription(await subRes.json());
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load settings",
        );
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSaving(true);

    try {
      const res = await fetch(`${API_BASE}/api/employer/profile`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          company_name: formData.company_name || undefined,
          company_size: formData.company_size || undefined,
          industry: formData.industry || undefined,
          company_website: formData.company_website || undefined,
          company_description: formData.company_description || undefined,
          billing_email: formData.billing_email || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to update profile");
      }

      const updated = await res.json();
      setProfile(updated);
      setSuccess("Profile updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUpgrade(tier: "starter" | "pro") {
    setIsUpgrading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/employer/billing/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ tier }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to create checkout session");
      }

      const data = await res.json();
      window.location.href = data.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upgrade failed");
      setIsUpgrading(false);
    }
  }

  async function handleManageSubscription() {
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/employer/billing/portal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to open subscription portal");
      }

      const data = await res.json();
      window.location.href = data.url;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not open portal",
      );
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
        <div className="h-96 animate-pulse rounded-xl border border-slate-200 bg-white" />
      </div>
    );
  }

  const currentTier = subscription?.tier || profile?.subscription_tier || "free";

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-slate-600">
          Manage your company profile and subscription
        </p>
      </div>

      {/* Current Plan Summary */}
      {subscription && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Current Plan
              </h2>
              <p className="mt-1 text-2xl font-bold capitalize text-slate-900">
                {subscription.tier} Plan
              </p>
              <p className="text-sm text-slate-500">
                Status:{" "}
                <span className="capitalize">{subscription.status}</span>
              </p>
              {subscription.current_period_end && (
                <p className="text-sm text-slate-500">
                  {subscription.cancel_at_period_end ? "Cancels" : "Renews"} on{" "}
                  {new Date(
                    subscription.current_period_end,
                  ).toLocaleDateString()}
                </p>
              )}
            </div>
            {subscription.has_subscription && (
              <button
                onClick={handleManageSubscription}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Manage Subscription
              </button>
            )}
          </div>
        </div>
      )}

      {/* Pricing Plans */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Subscription Plans
        </h2>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <PricingCard
            name="Free"
            price="$0"
            period="forever"
            features={[
              "1 active job posting",
              "10 candidate views/month",
              "Basic analytics",
            ]}
            current={currentTier === "free"}
            disabled={true}
            onSelect={() => {}}
          />
          <PricingCard
            name="Starter"
            price="$99"
            period="per month"
            features={[
              "5 active job postings",
              "50 candidate views/month",
              "Advanced analytics",
              "Priority email support",
            ]}
            current={currentTier === "starter"}
            disabled={isUpgrading || currentTier === "starter"}
            onSelect={() => handleUpgrade("starter")}
            buttonText={
              currentTier === "starter"
                ? "Current Plan"
                : currentTier === "pro"
                  ? "Downgrade"
                  : "Upgrade"
            }
          />
          <PricingCard
            name="Pro"
            price="$299"
            period="per month"
            features={[
              "Unlimited job postings",
              "200 candidate views/month",
              "Full analytics suite",
              "Priority support",
              "ATS integration",
            ]}
            current={currentTier === "pro"}
            disabled={isUpgrading || currentTier === "pro"}
            onSelect={() => handleUpgrade("pro")}
            buttonText={currentTier === "pro" ? "Current Plan" : "Upgrade"}
            recommended={true}
          />
        </div>

        {/* Enterprise */}
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-900 p-6 text-center text-white">
          <h3 className="text-xl font-bold">Enterprise</h3>
          <p className="mt-1 text-sm text-slate-300">
            Unlimited everything, dedicated support, custom integrations
          </p>
          <a
            href="mailto:sales@winnowcc.ai"
            className="mt-3 inline-block rounded-md bg-white px-5 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100"
          >
            Contact Sales
          </a>
        </div>
      </div>

      {/* Company Profile Form */}
      <form
        onSubmit={handleSave}
        className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 className="text-lg font-semibold text-slate-900">
          Company Profile
        </h2>

        {success && (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
            {success}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Name
            </label>
            <input
              type="text"
              value={formData.company_name}
              onChange={(e) =>
                setFormData({ ...formData, company_name: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Company Size
            </label>
            <select
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
              Website
            </label>
            <input
              type="url"
              value={formData.company_website}
              onChange={(e) =>
                setFormData({ ...formData, company_website: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Billing Email
            </label>
            <input
              type="email"
              value={formData.billing_email}
              onChange={(e) =>
                setFormData({ ...formData, billing_email: e.target.value })
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
          </div>
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
          />
        </div>

        <button
          type="submit"
          disabled={isSaving}
          className="rounded-md bg-slate-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isSaving ? "Saving..." : "Save Changes"}
        </button>
      </form>
    </div>
  );
}

function PricingCard({
  name,
  price,
  period,
  features,
  current,
  disabled,
  onSelect,
  buttonText = "Select Plan",
  recommended = false,
}: {
  name: string;
  price: string;
  period: string;
  features: string[];
  current: boolean;
  disabled: boolean;
  onSelect: () => void;
  buttonText?: string;
  recommended?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-5 ${
        recommended
          ? "border-blue-500 ring-1 ring-blue-500"
          : current
            ? "border-blue-500 bg-blue-50"
            : "border-slate-200 bg-slate-50"
      }`}
    >
      {recommended && (
        <span className="mb-2 inline-block rounded-full bg-blue-600 px-2.5 py-0.5 text-xs font-bold text-white">
          RECOMMENDED
        </span>
      )}

      <h3 className="text-xl font-bold text-slate-900">{name}</h3>
      <div className="mb-4 mt-3">
        <span className="text-3xl font-bold text-slate-900">{price}</span>
        <span className="ml-1 text-sm text-slate-500">{period}</span>
      </div>

      <ul className="mb-5 space-y-2">
        {features.map((feature) => (
          <li
            key={feature}
            className="flex items-start gap-2 text-sm text-slate-600"
          >
            <svg
              className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-emerald-500"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            {feature}
          </li>
        ))}
      </ul>

      <button
        onClick={onSelect}
        disabled={disabled}
        className={`w-full rounded-md py-2 text-sm font-medium ${
          current
            ? "bg-slate-100 text-slate-500"
            : disabled
              ? "bg-slate-200 text-slate-400"
              : recommended
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-slate-900 text-white hover:bg-slate-800"
        }`}
      >
        {current ? "Current Plan" : buttonText}
      </button>
    </div>
  );
}
