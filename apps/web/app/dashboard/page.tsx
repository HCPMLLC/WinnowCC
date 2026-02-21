"use client";

import { Suspense, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type DashboardMetrics = {
  profile_completeness_score: number;
  qualified_jobs_count: number;
  submitted_applications_count: number;
  interviews_requested_count: number;
  offers_received_count: number;
};

function DashboardPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const guard = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/login", redirectValue));
        return;
      }
      // Redirect non-candidate roles to their own dashboard
      if (me.role === "employer") {
        router.replace("/employer/dashboard");
        return;
      }
      if (me.role === "recruiter") {
        router.replace("/recruiter/dashboard");
        return;
      }
      if (!me.onboarding_complete) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/onboarding", redirectValue));
      }
    };
    void guard();
  }, [pathname, router, searchParams]);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/dashboard/metrics`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load dashboard metrics.");
        }
        const data = (await response.json()) as DashboardMetrics;
        setMetrics(data);
      } catch (caught) {
        const message =
          caught instanceof Error
            ? caught.message
            : "Failed to load dashboard metrics.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    void fetchMetrics();
  }, []);

  const getCompletenessColor = (score: number) => {
    if (score >= 80) return "text-green-600";
    if (score >= 50) return "text-amber-600";
    return "text-red-600";
  };

  const getCompletenessBarColor = (score: number) => {
    if (score >= 80) return "bg-green-500";
    if (score >= 50) return "bg-amber-500";
    return "bg-red-500";
  };

  return (
    <CandidateLayout>
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-2 text-slate-600">
          Your job search at a glance. Track your progress from profile to offer.
        </p>
      </header>

      {/* Error state */}
      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-xl border border-slate-200 bg-white p-6"
            >
              <div className="mb-3 h-4 w-24 rounded bg-slate-200"></div>
              <div className="h-8 w-16 rounded bg-slate-200"></div>
            </div>
          ))}
        </div>
      )}

      {/* Metrics grid */}
      {!loading && metrics && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {/* Profile Completeness */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-500">
                Profile Completeness
              </p>
              <svg
                className="h-5 w-5 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
            </div>
            <p
              className={`mt-2 text-3xl font-bold ${getCompletenessColor(metrics.profile_completeness_score)}`}
            >
              {metrics.profile_completeness_score}%
            </p>
            {/* Progress bar */}
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full ${getCompletenessBarColor(metrics.profile_completeness_score)} transition-all`}
                style={{ width: `${metrics.profile_completeness_score}%` }}
              ></div>
            </div>
            {metrics.profile_completeness_score < 80 && (
              <a
                href="/profile"
                className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                Complete your profile &rarr;
              </a>
            )}
          </div>

          {/* Qualified Jobs */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-500">Qualified Jobs</p>
              <svg
                className="h-5 w-5 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
            </div>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {metrics.qualified_jobs_count}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              jobs match your profile
            </p>
            <a
              href="/matches"
              className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              View matches &rarr;
            </a>
          </div>

          {/* Submitted Applications */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-500">
                Applications Submitted
              </p>
              <svg
                className="h-5 w-5 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {metrics.submitted_applications_count}
            </p>
            <p className="mt-1 text-sm text-slate-500">applications sent</p>
          </div>

          {/* Interviews Requested */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-500">
                Interviews Requested
              </p>
              <svg
                className="h-5 w-5 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </div>
            <p className="mt-2 text-3xl font-bold text-blue-600">
              {metrics.interviews_requested_count}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              employers want to talk
            </p>
          </div>

          {/* Offers Received */}
          <div className="rounded-xl border border-green-200 bg-green-50 p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-green-700">
                Offers Received
              </p>
              <svg
                className="h-5 w-5 text-green-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <p className="mt-2 text-3xl font-bold text-green-700">
              {metrics.offers_received_count}
            </p>
            <p className="mt-1 text-sm text-green-600">
              {metrics.offers_received_count === 1 ? "offer" : "offers"} received
            </p>
          </div>
        </div>
      )}

      {/* Quick actions */}
      {!loading && metrics && (
        <div className="mt-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Quick Actions
          </h2>
          <div className="flex flex-wrap gap-3">
            <a
              href="/matches"
              className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
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
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              Browse Job Matches
            </a>
            <a
              href="/profile"
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
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
              Edit Profile
            </a>
            <a
              href="/upload"
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
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                />
              </svg>
              Upload New Resume
            </a>
          </div>
        </div>
      )}

      {/* Recommendations to improve scores */}
      {!loading && metrics && (
        <div className="mt-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Recommendations to Improve Your Scores
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* Profile Completeness recommendations */}
            {metrics.profile_completeness_score < 100 && (
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-blue-100 p-2">
                    <svg
                      className="h-4 w-4 text-blue-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-medium text-blue-900">Complete Your Profile</h3>
                    <p className="mt-1 text-sm text-blue-700">
                      {metrics.profile_completeness_score < 50
                        ? "Add your skills, work history, and education to unlock better job matches."
                        : metrics.profile_completeness_score < 80
                          ? "Add more details to your experience and skills for higher match scores."
                          : "You're almost there! Fill in the remaining sections to reach 100%."}
                    </p>
                    <a
                      href="/profile"
                      className="mt-2 inline-block text-sm font-medium text-blue-600 hover:text-blue-800"
                    >
                      Edit profile &rarr;
                    </a>
                  </div>
                </div>
              </div>
            )}

            {/* Qualified Jobs recommendations */}
            {metrics.qualified_jobs_count < 10 && (
              <div className="rounded-xl border border-purple-200 bg-purple-50 p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-purple-100 p-2">
                    <svg
                      className="h-4 w-4 text-purple-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-medium text-purple-900">Expand Your Opportunities</h3>
                    <p className="mt-1 text-sm text-purple-700">
                      {metrics.qualified_jobs_count === 0
                        ? "Upload your resume and complete your profile to start seeing job matches."
                        : "Add more skills to your profile or consider related job titles to see more matches."}
                    </p>
                    <a
                      href="/profile"
                      className="mt-2 inline-block text-sm font-medium text-purple-600 hover:text-purple-800"
                    >
                      Update skills &rarr;
                    </a>
                  </div>
                </div>
              </div>
            )}

            {/* Applications recommendations */}
            {metrics.qualified_jobs_count > 0 && metrics.submitted_applications_count < 5 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-amber-100 p-2">
                    <svg
                      className="h-4 w-4 text-amber-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-medium text-amber-900">Apply to More Jobs</h3>
                    <p className="mt-1 text-sm text-amber-700">
                      You have {metrics.qualified_jobs_count} qualified matches. Apply within the first 10 days of posting for up to 8x better interview odds.
                    </p>
                    <a
                      href="/matches"
                      className="mt-2 inline-block text-sm font-medium text-amber-600 hover:text-amber-800"
                    >
                      View matches &rarr;
                    </a>
                  </div>
                </div>
              </div>
            )}

            {/* Interview rate recommendations */}
            {metrics.submitted_applications_count > 0 &&
              metrics.interviews_requested_count / metrics.submitted_applications_count < 0.1 && (
                <div className="rounded-xl border border-cyan-200 bg-cyan-50 p-4">
                  <div className="flex items-start gap-3">
                    <div className="rounded-full bg-cyan-100 p-2">
                      <svg
                        className="h-4 w-4 text-cyan-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="font-medium text-cyan-900">Boost Your Interview Rate</h3>
                      <p className="mt-1 text-sm text-cyan-700">
                        Referrals increase interview odds by 8x. Mark jobs where you have a connection and use tailored resumes for each application.
                      </p>
                      <a
                        href="/matches"
                        className="mt-2 inline-block text-sm font-medium text-cyan-600 hover:text-cyan-800"
                      >
                        Add referrals &rarr;
                      </a>
                    </div>
                  </div>
                </div>
              )}

            {/* Offer conversion recommendations */}
            {metrics.interviews_requested_count > 0 &&
              metrics.offers_received_count === 0 && (
                <div className="rounded-xl border border-green-200 bg-green-50 p-4">
                  <div className="flex items-start gap-3">
                    <div className="rounded-full bg-green-100 p-2">
                      <svg
                        className="h-4 w-4 text-green-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="font-medium text-green-900">Convert Interviews to Offers</h3>
                      <p className="mt-1 text-sm text-green-700">
                        You&apos;re getting interviews! Research each company thoroughly, prepare STAR stories, and follow up within 24 hours.
                      </p>
                    </div>
                  </div>
                </div>
              )}

            {/* All metrics looking good */}
            {metrics.profile_completeness_score >= 100 &&
              metrics.qualified_jobs_count >= 10 &&
              metrics.submitted_applications_count >= 5 &&
              (metrics.submitted_applications_count === 0 ||
                metrics.interviews_requested_count / metrics.submitted_applications_count >= 0.1) &&
              (metrics.interviews_requested_count === 0 || metrics.offers_received_count > 0) && (
                <div className="rounded-xl border border-green-200 bg-green-50 p-4 md:col-span-2 lg:col-span-3">
                  <div className="flex items-start gap-3">
                    <div className="rounded-full bg-green-100 p-2">
                      <svg
                        className="h-4 w-4 text-green-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="font-medium text-green-900">You&apos;re On Track!</h3>
                      <p className="mt-1 text-sm text-green-700">
                        Your job search is progressing well. Keep applying to high-match jobs and leveraging your referral network.
                      </p>
                    </div>
                  </div>
                </div>
              )}
          </div>
        </div>
      )}

      {/* Pro Tips */}
      {!loading && metrics && (
        <div className="mt-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            Pro Tips
          </h2>
          <div className="space-y-3">
            <CollapsibleTip title="Maximize Your Match Score">
              <ul className="list-disc space-y-1 pl-5">
                <li>Complete every section of your profile — skills, experience, education, and preferences all factor into your match score.</li>
                <li>Use the skill categories widget to organize your skills by proficiency level. Winnow weighs expert-level skills more heavily.</li>
                <li>Keep your job title preferences specific. &quot;Software Engineer&quot; matches better than &quot;Developer&quot; for engineering roles.</li>
              </ul>
            </CollapsibleTip>
            <CollapsibleTip title="Application Timing Matters">
              <ul className="list-disc space-y-1 pl-5">
                <li>Applying within the first 3 days of a posting gives you up to 4x better odds than applying after 2 weeks.</li>
                <li>Check your matches daily — new jobs are ingested every few hours from multiple sources.</li>
                <li>Use &quot;Prepare Materials&quot; to generate a tailored resume and cover letter before applying.</li>
              </ul>
            </CollapsibleTip>
            <CollapsibleTip title="Referrals Are Your Superpower">
              <ul className="list-disc space-y-1 pl-5">
                <li>A referral increases your interview probability by 8x — it&apos;s the single most impactful thing you can do.</li>
                <li>Mark any match where you know someone at the company. Even a loose connection counts.</li>
                <li>Ask your network proactively: &quot;I&apos;m interested in [Company]. Do you know anyone there?&quot;</li>
              </ul>
            </CollapsibleTip>
          </div>
        </div>
      )}

      {/* Pipeline visualization placeholder */}
      {!loading && metrics && (
        <div className="mt-8 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
          <p className="text-sm text-slate-500">
            Pipeline visualization and detailed tracking coming soon.
          </p>
        </div>
      )}
    </CandidateLayout>
  );
}

export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardPageContent />
    </Suspense>
  );
}
