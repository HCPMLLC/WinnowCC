"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { useState } from "react";

// --- Link definitions ---
const CANDIDATE_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/matches", label: "Matches" },
  { href: "/profile", label: "Profile" },
  { href: "/insights", label: "Insights" },
  { href: "/settings", label: "Settings" },
];

const EMPLOYER_LINKS = [
  { href: "/employer/dashboard", label: "Dashboard" },
  { href: "/employer/jobs", label: "Jobs" },
  { href: "/employer/candidates", label: "Candidates" },
  { href: "/employer/settings", label: "Settings" },
];

const RECRUITER_LINKS = [
  { href: "/recruiter/dashboard", label: "Dashboard" },
  { href: "/recruiter/jobs", label: "Jobs" },
  { href: "/recruiter/clients", label: "Clients" },
  { href: "/recruiter/pipeline", label: "Pipeline" },
  { href: "/recruiter/candidates", label: "Candidates" },
];

const ADMIN_LINKS = [
  { href: "/admin/trust", label: "Trust Queue" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/job-quality", label: "Job Quality" },
  { href: "/admin/candidates", label: "Candidates" },
];

export default function Navbar() {
  const { user, loading, isAdmin, isCandidate, isEmployer, isRecruiter } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Don't show navbar on public pages or while loading
  const isPublicPage =
    pathname === "/" || pathname === "/login" || pathname === "/signup";
  if (loading) return null;
  if (!user || isPublicPage) return null;

  const handleLogout = async () => {
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api/auth/logout`,
        { method: "POST", credentials: "include" },
      );
    } catch {
      // Logout even if the API call fails
    }
    // Clear web-domain session cookie
    await fetch("/api/auth/session", { method: "DELETE" }).catch(() => {});
    router.push("/login");
  };

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  const homeHref = isRecruiter
    ? "/recruiter/dashboard"
    : isEmployer
      ? "/employer/dashboard"
      : "/dashboard";

  return (
    <nav className="bg-slate-900 text-white shadow-lg">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo / Brand */}
          <div className="flex-shrink-0">
            <Link href={homeHref}>
              <Image
                src="/Winnow CC Masthead TBGC.png"
                alt="Winnow"
                width={138}
                height={46}
                className="h-[2.588rem] w-auto"
                priority
              />
            </Link>
          </div>

          {/* Desktop links */}
          <div className="hidden items-center space-x-1 md:flex">
            {/* Candidate links — only shown for candidate/both role */}
            {isCandidate &&
              CANDIDATE_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive(link.href)
                      ? "bg-slate-700 text-amber-400"
                      : "text-gray-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  {link.label}
                </Link>
              ))}

            {/* Employer section — only shown for employer/both role */}
            {isEmployer && (
              <>
                {isCandidate && <div className="mx-2 h-6 w-px bg-slate-600" />}
                <span className="mr-1 text-xs uppercase tracking-wider text-slate-500">
                  Employer
                </span>
                {EMPLOYER_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive(link.href)
                        ? "bg-blue-900/50 text-blue-300"
                        : "text-blue-400/70 hover:bg-slate-800 hover:text-blue-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}

            {/* Recruiter section — only shown for recruiter role */}
            {isRecruiter && (
              <>
                <div className="mx-2 h-6 w-px bg-slate-600" />
                <span className="mr-1 text-xs uppercase tracking-wider text-slate-500">
                  Recruiter
                </span>
                {RECRUITER_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive(link.href)
                        ? "bg-emerald-900/50 text-emerald-300"
                        : "text-emerald-400/70 hover:bg-slate-800 hover:text-emerald-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}

            {/* Admin section — only shown if user.is_admin */}
            {isAdmin && (
              <>
                <div className="mx-2 h-6 w-px bg-slate-600" /> {/* Divider */}
                <span className="mr-1 text-xs uppercase tracking-wider text-slate-500">
                  Admin
                </span>
                {ADMIN_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive(link.href)
                        ? "bg-red-900/50 text-red-300"
                        : "text-red-400/70 hover:bg-slate-800 hover:text-red-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}
          </div>

          {/* Right side: user info + logout */}
          <div className="hidden items-center space-x-4 md:flex">
            <span className="text-sm text-gray-400">{user.email}</span>
            {isAdmin && (
              <span className="rounded-full bg-red-900/50 px-2 py-0.5 text-xs text-red-300">
                Admin
              </span>
            )}
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 transition-colors hover:text-white"
            >
              Logout
            </button>
          </div>

          {/* Mobile hamburger button */}
          <div className="md:hidden">
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="text-gray-400 hover:text-white focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              <svg
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                {mobileOpen ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {mobileOpen && (
        <div className="border-t border-slate-700 md:hidden">
          <div className="space-y-1 px-2 pb-3 pt-2">
            {isCandidate &&
              CANDIDATE_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={`block rounded-md px-3 py-2 text-base font-medium ${
                    isActive(link.href)
                      ? "bg-slate-700 text-amber-400"
                      : "text-gray-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  {link.label}
                </Link>
              ))}

            {isEmployer && (
              <>
                <div className="my-2 border-t border-slate-700" />
                <p className="px-3 text-xs uppercase tracking-wider text-slate-500">
                  Employer
                </p>
                {EMPLOYER_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={`block rounded-md px-3 py-2 text-base font-medium ${
                      isActive(link.href)
                        ? "bg-blue-900/50 text-blue-300"
                        : "text-blue-400/70 hover:bg-slate-800 hover:text-blue-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}

            {isRecruiter && (
              <>
                <div className="my-2 border-t border-slate-700" />
                <p className="px-3 text-xs uppercase tracking-wider text-slate-500">
                  Recruiter
                </p>
                {RECRUITER_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={`block rounded-md px-3 py-2 text-base font-medium ${
                      isActive(link.href)
                        ? "bg-emerald-900/50 text-emerald-300"
                        : "text-emerald-400/70 hover:bg-slate-800 hover:text-emerald-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}

            {isAdmin && (
              <>
                <div className="my-2 border-t border-slate-700" />
                <p className="px-3 text-xs uppercase tracking-wider text-slate-500">
                  Admin
                </p>
                {ADMIN_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={`block rounded-md px-3 py-2 text-base font-medium ${
                      isActive(link.href)
                        ? "bg-red-900/50 text-red-300"
                        : "text-red-400/70 hover:bg-slate-800 hover:text-red-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}

            <div className="my-2 border-t border-slate-700" />
            <div className="px-3 py-2">
              <p className="text-sm text-gray-400">{user.email}</p>
              <button
                onClick={handleLogout}
                className="mt-2 text-sm text-gray-400 hover:text-white"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
