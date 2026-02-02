"use client";

import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";

import { withRedirectParam } from "../lib/redirects";

function LoginRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect") || searchParams.get("next");

  useEffect(() => {
    // Redirect to landing page with the redirect param preserved
    if (redirectParam) {
      router.replace(withRedirectParam("/", redirectParam));
    } else {
      router.replace("/");
    }
  }, [router, redirectParam]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-sm text-slate-500">Redirecting...</div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-sm text-slate-500">Loading...</div>
        </div>
      }
    >
      <LoginRedirect />
    </Suspense>
  );
}
