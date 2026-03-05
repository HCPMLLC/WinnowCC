"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";

type AdminNavItem = {
  href: string;
  label: string;
  exact?: boolean;
  badge?: number;
};

type AdminNavSection = {
  label: string;
  items: AdminNavItem[];
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [failedCount, setFailedCount] = useState(0);

  const fetchFailedCount = useCallback(async () => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/admin/support/queue-monitor`,
        { credentials: "include" }
      );
      if (!res.ok) return;
      const data = await res.json();
      const total = (data.queues || []).reduce(
        (sum: number, q: { failed?: number }) => sum + (q.failed || 0),
        0
      );
      setFailedCount(total);
    } catch {
      // Silently ignore — sidebar shouldn't break if API is down
    }
  }, []);

  useEffect(() => {
    if (!loading && (!user || !isAdmin)) {
      router.push("/dashboard");
    }
  }, [user, loading, isAdmin, router]);

  useEffect(() => {
    if (!isAdmin) return;
    fetchFailedCount();
    const interval = setInterval(fetchFailedCount, 60_000);
    return () => clearInterval(interval);
  }, [isAdmin, fetchFailedCount]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");

  const ADMIN_SECTIONS: AdminNavSection[] = [
    {
      label: "Platform",
      items: [
        { href: "/admin/kpi", label: "KPI Dashboard" },
        { href: "/admin/profile", label: "Users" },
        { href: "/admin/candidates", label: "Candidates" },
        { href: "/admin/employers", label: "Employers" },
        { href: "/admin/recruiters", label: "Recruiters" },
        { href: "/admin/jobs", label: "Jobs" },
        { href: "/admin/job-quality", label: "Job Quality" },
        { href: "/admin/forms", label: "Forms" },
      ],
    },
    {
      label: "Trust & Compliance",
      items: [
        { href: "/admin/trust", label: "Trust Queue" },
        { href: "/admin/support/audit", label: "Audit Log" },
        { href: "/admin/settings", label: "Settings" },
      ],
    },
    {
      label: "Operations",
      items: [
        { href: "/admin/support", label: "Support Overview", exact: true },
        { href: "/admin/support/lookup", label: "User Lookup" },
        { href: "/admin/support/billing", label: "Billing" },
        { href: "/admin/support/queues", label: "Queues", badge: failedCount },
        { href: "/admin/support/scheduler", label: "Scheduler" },
        { href: "/admin/support/usage", label: "Usage" },
        { href: "/admin/support/tickets", label: "Tickets" },
      ],
    },
  ];

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex gap-8">
        {/* Sidebar nav */}
        <aside className="hidden w-48 flex-shrink-0 lg:block">
          <nav className="sticky top-6 space-y-1">
            {ADMIN_SECTIONS.map((section) => (
              <div key={section.label}>
                <p className="mb-1 px-3 pt-4 text-xs font-semibold uppercase tracking-wider text-slate-400 first:pt-0">
                  {section.label}
                </p>
                {section.items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive(item.href, item.exact)
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    {item.label}
                    {item.badge != null && item.badge > 0 && (
                      <span className="ml-auto inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-red-600 px-1.5 py-0.5 text-xs font-semibold leading-none text-white">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
