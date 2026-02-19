"use client";

import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";

function SignupRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect");

  useEffect(() => {
    const url = redirectParam
      ? `/login?mode=signup&redirect=${encodeURIComponent(redirectParam)}`
      : "/login?mode=signup";
    router.replace(url);
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
