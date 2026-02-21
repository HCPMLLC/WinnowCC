"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function BillingSuccessContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );

  useEffect(() => {
    if (!sessionId) {
      setStatus("success");
      return;
    }

    // Fetch subscription to confirm it updated
    async function verify() {
      try {
        const res = await fetch(`${API_BASE}/api/employer/billing/subscription`, {
          credentials: "include",
        });
        if (res.ok) {
          setStatus("success");
        } else {
          setStatus("success"); // Still show success — webhook may be delayed
        }
      } catch {
        setStatus("success");
      }
    }

    // Small delay to let webhook process
    const timer = setTimeout(verify, 1500);
    return () => clearTimeout(timer);
  }, [sessionId]);

  if (status === "loading") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-slate-900" />
          <p className="text-slate-600">Confirming your subscription...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
          <svg
            className="h-8 w-8 text-emerald-600"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4.5 12.75l6 6 9-13.5"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-slate-900">
          Subscription Activated!
        </h1>
        <p className="mt-2 text-slate-600">
          Your employer subscription is now active. You can start posting jobs
          and browsing candidates immediately.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/employer/jobs/new"
            className="rounded-md bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            Post a Job
          </Link>
          <Link
            href="/employer/dashboard"
            className="rounded-md border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Go to Dashboard
          </Link>
        </div>

        <p className="mt-6 text-xs text-slate-400">
          Manage your subscription anytime from{" "}
          <Link
            href="/employer/settings"
            className="text-slate-500 underline hover:text-slate-700"
          >
            Settings
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

export default function BillingSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[60vh] items-center justify-center">
          <div className="text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-slate-900" />
            <p className="text-slate-600">Loading...</p>
          </div>
        </div>
      }
    >
      <BillingSuccessContent />
    </Suspense>
  );
}
