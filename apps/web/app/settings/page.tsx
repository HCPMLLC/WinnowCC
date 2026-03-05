"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";
import UsageMeter from "../components/UsageMeter";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface ExportPreview {
  profile_versions: number;
  resume_documents: number;
  matches: number;
  tailored_resumes: number;
  has_trust_record: boolean;
}

interface UsageSummary {
  match_refreshes: number;
  tailor_requests: number;
  sieve_messages_today: number;
  semantic_searches_today: number;
}

interface FeatureAccess {
  data_export: boolean;
  career_intelligence: boolean;
  ips_detail: string;
}

interface BillingStatus {
  plan_tier: string;
  billing_cycle: string | null;
  subscription_status: string | null;
  match_refreshes_used: number;
  match_refreshes_limit: number | null;
  tailor_requests_used: number;
  tailor_requests_limit: number | null;
  usage?: UsageSummary;
  limits?: Record<string, unknown>;
  features?: FeatureAccess;
}

function SettingsContent() {
  const searchParams = useSearchParams();
  const [toast, setToast] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [billingLoading, setBillingLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState(false);
  const [deleteInput, setDeleteInput] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openToIntros, setOpenToIntros] = useState(true);
  const [introToggling, setIntroToggling] = useState(false);

  // Phone & SMS state
  const [smsPhone, setSmsPhone] = useState("");
  const [smsConsent, setSmsConsent] = useState(false);
  const [smsPhoneLoaded, setSmsPhoneLoaded] = useState("");
  const [smsConsentLoaded, setSmsConsentLoaded] = useState(false);
  const [smsLoading, setSmsLoading] = useState(true);
  const [smsSaving, setSmsSaving] = useState(false);

  const fetchBilling = () =>
    fetch(`${API_BASE}/api/billing/status`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load billing");
        return r.json();
      })
      .then((data) => {
        setBilling(data);
        return data as BillingStatus;
      })
      .catch(() => {
        setBilling(null);
        return null;
      })
      .finally(() => setBillingLoading(false));

  // Handle Stripe return params — poll until webhook has processed
  useEffect(() => {
    const billingParam = searchParams.get("billing");
    if (billingParam === "success") {
      setToast("Your subscription is now active!");
      // Stripe webhook may take a few seconds; poll up to 15s
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        const data = await fetchBilling();
        if ((data?.plan_tier && data.plan_tier !== "free") || attempts >= 5) {
          clearInterval(poll);
        }
      }, 3000);
      return () => clearInterval(poll);
    } else if (billingParam === "canceled") {
      setToast("Checkout was canceled. You can upgrade anytime.");
    }
  }, [searchParams]);

  // Load billing status
  useEffect(() => {
    fetchBilling();
  }, []);

  // Load introduction preferences
  useEffect(() => {
    fetch(`${API_BASE}/api/profile/introductions/count`, { credentials: "include" })
      .then(() => {
        // If the profile endpoint works, the user has a profile
        // We don't have a GET for the boolean itself, so we default to true
        // and let the PATCH endpoint update it
      })
      .catch(() => {});
  }, []);

  // Load export preview
  useEffect(() => {
    fetch(`${API_BASE}/api/account/export/preview`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load preview");
        return r.json();
      })
      .then((data) => setPreview(data))
      .catch(() => setPreview(null))
      .finally(() => setPreviewLoading(false));
  }, []);

  // Load SMS consent status
  useEffect(() => {
    fetch(`${API_BASE}/api/onboarding/sms-consent-status`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load SMS status");
        return r.json();
      })
      .then((data) => {
        const ph = data.phone || "";
        const sc = Boolean(data.sms_consent);
        setSmsPhone(ph);
        setSmsConsent(sc);
        setSmsPhoneLoaded(ph);
        setSmsConsentLoaded(sc);
      })
      .catch(() => {})
      .finally(() => setSmsLoading(false));
  }, []);

  const handleCheckout = async (tier: string, interval: string) => {
    setCheckoutLoading(`${tier}-${interval}`);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/billing/unified-checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segment: "candidate", tier, interval }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Checkout failed");
      }
      const { checkout_url } = await res.json();
      window.location.href = checkout_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
      setCheckoutLoading(null);
    }
  };

  const handlePortal = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Could not open billing portal");
      }
      const { portal_url } = await res.json();
      window.location.href = portal_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Portal failed");
    }
  };

  const handleExport = async () => {
    setExportLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/account/export`, {
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Export failed");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "winnow-export.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setToast("Your data has been downloaded as winnow-export.zip.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExportLoading(false);
    }
  };

  const handleDelete = async () => {
    setDeleteLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/account/delete`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: "DELETE MY ACCOUNT" }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Deletion failed");
      }
      window.location.href = "/";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deletion failed");
      setDeleteLoading(false);
      setShowConfirmDialog(false);
    }
  };

  const canDelete = deleteInput === "DELETE MY ACCOUNT";
  const isPro = billing?.plan_tier === "pro";
  const isStarter = billing?.plan_tier === "starter";
  const isPaid = isPro || isStarter;

  return (
    <CandidateLayout>
      <CollapsibleTip title="Your Account" defaultOpen={false}>
        <p>
          Manage your subscription, export your data, or update your
          preferences. Your data is always yours — export anytime.
        </p>
      </CollapsibleTip>

      <div className="mt-6">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-slate-900">
            Account Settings
          </h1>
          <a
            href="/dashboard"
            className="text-sm font-medium text-slate-600 hover:text-slate-900"
          >
            Back to Dashboard
          </a>
        </div>

        {/* Toast */}
        {toast && (
          <div className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            {toast}
            <button
              onClick={() => setToast(null)}
              className="ml-2 font-medium underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </div>
        )}

        {/* Billing Section */}
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-lg font-semibold text-slate-900">
            Subscription &amp; Billing
          </h2>

          {billingLoading ? (
            <p className="mt-4 text-sm text-slate-400">
              Loading billing info...
            </p>
          ) : billing ? (
            <div className="mt-4">
              {/* Plan badge */}
              <div className="mb-4 flex items-center gap-3">
                <span className="text-sm text-slate-600">Current Plan:</span>
                {isPro ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">
                    PRO
                  </span>
                ) : isStarter ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-800">
                    STARTER
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
                    FREE
                  </span>
                )}
                {isPaid && billing.billing_cycle && (
                  <span className="text-sm text-slate-500">
                    ({billing.billing_cycle})
                  </span>
                )}
              </div>

              {/* Usage bars */}
              <div className="mb-6 space-y-3">
                <UsageMeter
                  label="Tailored Resumes"
                  used={billing.tailor_requests_used}
                  limit={billing.tailor_requests_limit}
                />
                <UsageMeter
                  label="Match Refreshes"
                  used={billing.match_refreshes_used}
                  limit={billing.match_refreshes_limit}
                />
                {billing.usage && billing.limits && (
                  <>
                    <UsageMeter
                      label="Sieve Messages"
                      period="(today)"
                      used={billing.usage.sieve_messages_today}
                      limit={
                        typeof billing.limits.sieve_messages_per_day === "number" &&
                        (billing.limits.sieve_messages_per_day as number) < 9999
                          ? (billing.limits.sieve_messages_per_day as number)
                          : null
                      }
                    />
                    <UsageMeter
                      label="Semantic Searches"
                      period="(today)"
                      used={billing.usage.semantic_searches_today}
                      limit={
                        typeof billing.limits.semantic_searches_per_day === "number" &&
                        (billing.limits.semantic_searches_per_day as number) < 9999
                          ? (billing.limits.semantic_searches_per_day as number)
                          : null
                      }
                    />
                  </>
                )}
              </div>

              {/* Feature access */}
              {billing.features && (
                <div className="mb-6 flex flex-wrap gap-2">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      billing.features.data_export
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-400"
                    }`}
                  >
                    Data Export
                  </span>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      billing.features.career_intelligence
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-400"
                    }`}
                  >
                    Career Intelligence
                  </span>
                  <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
                    IPS: {billing.features.ips_detail.replace(/_/g, " ")}
                  </span>
                </div>
              )}

              {/* Actions */}
              {isPaid ? (
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={handlePortal}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                      />
                    </svg>
                    Manage Billing
                  </button>
                  {isStarter && (
                    <button
                      onClick={() => handleCheckout("pro", "monthly")}
                      disabled={checkoutLoading !== null}
                      className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-amber-400 disabled:opacity-50"
                    >
                      {checkoutLoading === "pro-monthly"
                        ? "Redirecting..."
                        : "Upgrade to Pro \u2014 $29/mo"}
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={() => handleCheckout("starter", "monthly")}
                      disabled={checkoutLoading !== null}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {checkoutLoading === "starter-monthly"
                        ? "Redirecting..."
                        : "Starter \u2014 $9/mo"}
                    </button>
                    <button
                      onClick={() => handleCheckout("starter", "annual")}
                      disabled={checkoutLoading !== null}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {checkoutLoading === "starter-annual"
                        ? "Redirecting..."
                        : "Starter Annual \u2014 $79/yr"}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={() => handleCheckout("pro", "monthly")}
                      disabled={checkoutLoading !== null}
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                    >
                      {checkoutLoading === "pro-monthly"
                        ? "Redirecting..."
                        : "Upgrade to Pro \u2014 $29/mo"}
                    </button>
                    <button
                      onClick={() => handleCheckout("pro", "annual")}
                      disabled={checkoutLoading !== null}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {checkoutLoading === "pro-annual"
                        ? "Redirecting..."
                        : "Pro Annual \u2014 $249/yr (save 28%)"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">
              Complete onboarding to see billing info.
            </p>
          )}
        </div>

        {/* Divider */}
        <hr className="mb-8 border-slate-200" />

        {/* Export Section */}
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-lg font-semibold text-slate-900">
            Export My Data
          </h2>
          <p className="mb-4 text-sm text-slate-500">
            Download a ZIP file containing all your Winnow data.
          </p>

          <ul className="mb-4 space-y-1 text-sm text-slate-600">
            <li>Profile (all versions)</li>
            <li>Uploaded resumes</li>
            <li>Generated tailored resumes and cover letters</li>
            <li>Match history and scores</li>
            <li>Trust and consent records</li>
            <li>Usage history</li>
          </ul>

          {previewLoading ? (
            <p className="mb-4 text-sm text-slate-400">
              Loading data summary...
            </p>
          ) : preview ? (
            <div className="mb-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
              Your data: {preview.profile_versions} profile version
              {preview.profile_versions !== 1 && "s"},{" "}
              {preview.resume_documents} resume
              {preview.resume_documents !== 1 && "s"}, {preview.matches} match
              {preview.matches !== 1 && "es"}, {preview.tailored_resumes}{" "}
              tailored resume{preview.tailored_resumes !== 1 && "s"}
              {preview.has_trust_record && ", trust record"}
            </div>
          ) : null}

          {billing?.features && !billing.features.data_export ? (
            <p className="text-sm text-slate-500">
              Data export is available on Starter and Pro plans.{" "}
              <button
                onClick={() => handleCheckout("starter", "monthly")}
                className="font-medium text-slate-900 underline hover:text-slate-700"
              >
                Upgrade to unlock
              </button>
            </p>
          ) : (
            <button
              onClick={handleExport}
              disabled={exportLoading}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {exportLoading ? (
                <>
                  <svg
                    className="h-4 w-4 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  Download My Data
                </>
              )}
            </button>
          )}
        </div>

        {/* Introduction Preferences */}
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-lg font-semibold text-slate-900">
            Recruiter Introductions
          </h2>
          <p className="mb-4 text-sm text-slate-500">
            Control whether recruiters can request an introduction. You always decide whether to accept and share your contact details.
          </p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">Open to Introductions</p>
              <p className="text-xs text-slate-400">
                Allow recruiters to send you introduction requests
              </p>
            </div>
            <button
              disabled={introToggling}
              onClick={async () => {
                setIntroToggling(true);
                try {
                  const res = await fetch(`${API_BASE}/api/profile/introduction-preferences`, {
                    method: "PATCH",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ open_to_introductions: !openToIntros }),
                  });
                  if (res.ok) {
                    const data = await res.json();
                    setOpenToIntros(data.open_to_introductions);
                    setToast(data.open_to_introductions
                      ? "You are now open to recruiter introductions."
                      : "Recruiter introductions are now disabled.");
                  }
                } catch { /* ignore */ }
                finally { setIntroToggling(false); }
              }}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 ${
                openToIntros ? "bg-emerald-500" : "bg-slate-300"
              } disabled:opacity-50`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  openToIntros ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Phone & SMS Notifications */}
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-lg font-semibold text-slate-900">
            Phone &amp; SMS Notifications
          </h2>
          <p className="mb-4 text-sm text-slate-500">
            Receive text message alerts about job matches and application updates.
          </p>

          {smsLoading ? (
            <p className="text-sm text-slate-400">Loading SMS preferences...</p>
          ) : (
            <div className="flex flex-col gap-4">
              <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                Phone Number
                <input
                  type="tel"
                  value={smsPhone}
                  onChange={(e) => {
                    setSmsPhone(e.target.value);
                    if (!e.target.value.trim()) setSmsConsent(false);
                  }}
                  placeholder="(210) 555-1234"
                  className="max-w-xs rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </label>
              <label className={`flex items-start gap-3 text-sm ${!smsPhone.trim() ? "opacity-50" : ""}`}>
                <input
                  type="checkbox"
                  checked={smsConsent}
                  onChange={(e) => setSmsConsent(e.target.checked)}
                  disabled={!smsPhone.trim()}
                  className="mt-1"
                />
                <span className="text-slate-700">
                  I agree to receive automated text messages from Winnow about job matches,
                  application updates, and career alerts at the phone number provided. Message
                  frequency varies. Standard Msg &amp; data rates may apply. Reply STOP to opt
                  out or HELP for help. We will not share your mobile information with third
                  parties for promotional or marketing purposes. See our{" "}
                  <a href="/terms" target="_blank" className="font-semibold underline hover:text-slate-900">
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a href="/privacy" target="_blank" className="font-semibold underline hover:text-slate-900">
                    Privacy Policy
                  </a>
                  . Consent is not required to use Winnow.
                </span>
              </label>
              {(smsPhone !== smsPhoneLoaded || smsConsent !== smsConsentLoaded) && (
                <button
                  disabled={smsSaving}
                  onClick={async () => {
                    setSmsSaving(true);
                    setError(null);
                    try {
                      const res = await fetch(`${API_BASE}/api/onboarding/sms-consent`, {
                        method: "PUT",
                        credentials: "include",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          phone: smsPhone.trim() || null,
                          sms_consent: smsConsent,
                        }),
                      });
                      if (!res.ok) {
                        const data = await res.json().catch(() => null);
                        throw new Error(data?.detail || "Failed to save SMS preferences");
                      }
                      const data = await res.json();
                      const ph = data.phone || "";
                      const sc = Boolean(data.sms_consent);
                      setSmsPhone(ph);
                      setSmsConsent(sc);
                      setSmsPhoneLoaded(ph);
                      setSmsConsentLoaded(sc);
                      setToast(sc ? "SMS notifications enabled." : "SMS preferences saved.");
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Failed to save SMS preferences");
                    } finally {
                      setSmsSaving(false);
                    }
                  }}
                  className="w-fit inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  {smsSaving ? "Saving..." : "Save Changes"}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Divider */}
        <hr className="mb-8 border-slate-200" />

        {/* Delete Section */}
        <div className="rounded-xl border border-red-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-lg font-semibold text-red-700">
            Delete My Account
          </h2>
          <p className="mb-4 text-sm text-red-600">
            This action is permanent and cannot be undone.
          </p>

          <div className="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800">
            <p className="mb-2 font-medium">
              Deleting your account will permanently remove:
            </p>
            <ul className="space-y-1 pl-4">
              <li>Your profile and all versions</li>
              <li>All uploaded resume files</li>
              <li>All generated tailored resumes</li>
              <li>Your match history and scores</li>
              <li>Your login credentials</li>
            </ul>
            <p className="mt-3 font-medium">
              We recommend downloading your data first.
            </p>
          </div>

          <label className="mb-2 block text-sm font-medium text-slate-700">
            Type <span className="font-mono">DELETE MY ACCOUNT</span> to
            confirm:
          </label>
          <input
            type="text"
            value={deleteInput}
            onChange={(e) => setDeleteInput(e.target.value)}
            placeholder="DELETE MY ACCOUNT"
            className="mb-4 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
          />

          <button
            onClick={() => setShowConfirmDialog(true)}
            disabled={!canDelete || deleteLoading}
            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleteLoading ? "Deleting..." : "Delete My Account"}
          </button>
        </div>

        {/* Confirmation dialog */}
        {showConfirmDialog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
              <h3 className="mb-2 text-lg font-bold text-red-700">
                Are you absolutely sure?
              </h3>
              <p className="mb-4 text-sm text-slate-600">
                This cannot be undone. All your data will be permanently deleted
                and you will be logged out immediately.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowConfirmDialog(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleteLoading}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteLoading ? "Deleting..." : "Yes, Delete Everything"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </CandidateLayout>
  );
}

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsContent />
    </Suspense>
  );
}
