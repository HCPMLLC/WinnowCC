"use client";

import { useEffect, useState } from "react";

const CONSENT_KEY = "winnow_cookie_consent";

type ConsentStatus = "pending" | "accepted" | "rejected";

function getStoredConsent(): ConsentStatus {
  if (typeof window === "undefined") return "pending";
  return (localStorage.getItem(CONSENT_KEY) as ConsentStatus) || "pending";
}

export default function CookieConsent() {
  const [status, setStatus] = useState<ConsentStatus>("pending");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setStatus(getStoredConsent());
  }, []);

  if (!mounted || status !== "pending") return null;

  const accept = () => {
    localStorage.setItem(CONSENT_KEY, "accepted");
    setStatus("accepted");
  };

  const reject = () => {
    localStorage.setItem(CONSENT_KEY, "rejected");
    setStatus("rejected");
  };

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-gray-200 bg-white px-4 py-4 shadow-lg sm:px-6"
    >
      <div className="mx-auto flex max-w-5xl flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-4">
        <p className="flex-1 text-sm text-gray-700">
          We use cookies for error tracking and analytics to improve your
          experience. By clicking &ldquo;Accept&rdquo;, you consent to the use
          of non-essential cookies.{" "}
          <a href="/privacy" className="underline hover:text-blue-600">
            Privacy Policy
          </a>
        </p>
        <div className="flex gap-2">
          <button
            onClick={reject}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 transition hover:bg-gray-50"
          >
            Reject
          </button>
          <button
            onClick={accept}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}

/** Check if analytics consent has been given (for use by analytics init). */
export function hasAnalyticsConsent(): boolean {
  return getStoredConsent() === "accepted";
}
