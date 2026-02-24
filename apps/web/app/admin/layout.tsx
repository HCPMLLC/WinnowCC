"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

const ADMIN_NAV = [
  { href: "/admin/profile", label: "Users" },
  { href: "/admin/candidates", label: "Candidates" },
  { href: "/admin/employers", label: "Employers" },
  { href: "/admin/recruiters", label: "Recruiters" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/job-quality", label: "Job Quality" },
  { href: "/admin/trust", label: "Trust" },
  { href: "/admin/forms", label: "Forms" },
];

const SUPPORT_NAV = [
  { href: "/admin/support", label: "Overview", exact: true },
  { href: "/admin/support/lookup", label: "User Lookup" },
  { href: "/admin/support/billing", label: "Billing" },
  { href: "/admin/support/queues", label: "Queues" },
  { href: "/admin/support/scheduler", label: "Scheduler" },
  { href: "/admin/support/usage", label: "Usage" },
  { href: "/admin/support/audit", label: "Audit Log" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && (!user || !isAdmin)) {
      router.push("/dashboard");
    }
  }, [user, loading, isAdmin, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!isAdmin) {
    return null; // Will redirect via the useEffect above
  }

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex gap-8">
        {/* Sidebar nav */}
        <aside className="hidden w-44 flex-shrink-0 lg:block">
          <nav className="sticky top-6 space-y-1">
            <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Admin
            </p>
            {ADMIN_NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive(item.href)
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {item.label}
              </Link>
            ))}
            <p className="mb-3 mt-6 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Support
            </p>
            {SUPPORT_NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  ("exact" in item ? pathname === item.href : isActive(item.href))
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
