"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    const guard = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        router.replace("/login");
        return;
      }
      if (!me.onboarding_complete) {
        router.replace("/onboarding");
      }
    };
    void guard();
  }, [router]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-16">
      <header>
        <h1 className="text-3xl font-semibold">Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">
          Placeholder workspace. Authentication and data wiring will arrive next.
        </p>
      </header>

      <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <p className="text-sm text-slate-600">
          Add candidate comparisons, scorecards, and pipeline views here.
        </p>
      </section>
    </main>
  );
}
