"use client";

import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";

import { withRedirectParam } from "../lib/redirects";

function SignupRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect");

  useEffect(() => {
    // Redirect to landing page signup section
    const baseUrl = "/#signup-section";
    if (redirectParam) {
      router.replace(`/?redirect=${encodeURIComponent(redirectParam)}#signup-section`);
    } else {
      router.replace(baseUrl);
    }
  }, [router, redirectParam]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-sm text-slate-500">Redirecting...</div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-sm text-slate-500">Loading...</div>
        </div>
      }
    >
      <SignupRedirect />
    </Suspense>
  );
}
