"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface IntroductionItem {
  id: number;
  candidate_profile_id: number;
  employer_job_id: number | null;
  message: string;
  status: string;
  candidate_response_message: string | null;
  created_at: string | null;
  responded_at: string | null;
  expires_at: string | null;
  candidate_name: string | null;
  candidate_headline: string | null;
  candidate_location: string | null;
  candidate_email: string | null;
  job_title: string | null;
}

interface UsageInfo {
  used: number;
  limit: number;
  tier: string;
}

const STATUS_TABS = ["all", "pending", "accepted", "declined", "expired"];

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    accepted: "bg-green-100 text-green-800",
    declined: "bg-red-100 text-red-800",
    expired: "bg-slate-100 text-slate-500",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] || "bg-slate-100 text-slate-500"}`}
    >
      {status}
    </span>
  );
}

export default function EmployerIntroductionsPage() {
  const [intros, setIntros] = useState<IntroductionItem[]>([]);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [activeTab, setActiveTab] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const statusParam =
          activeTab === "all" ? "" : `?status=${activeTab}`;
        const [introsRes, usageRes] = await Promise.all([
          fetch(`${API_BASE}/api/employer/introductions${statusParam}`, {
            credentials: "include",
          }),
          fetch(`${API_BASE}/api/employer/introductions/usage`, {
            credentials: "include",
          }),
        ]);
        if (!introsRes.ok) {
          const data = await introsRes.json().catch(() => null);
          throw new Error(data?.detail || "Failed to load introductions");
        }
        setIntros(await introsRes.json());
        if (usageRes.ok) {
          setUsage(await usageRes.json());
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load introductions",
        );
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [activeTab]);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Introductions</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage your introduction requests to candidates
          </p>
        </div>
        {usage && (
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm">
            <span className="font-medium text-slate-900">{usage.used}</span>
            <span className="text-slate-500"> of </span>
            <span className="font-medium text-slate-900">{usage.limit}</span>
            <span className="text-slate-500"> intros used this month</span>
          </div>
        )}
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
              activeTab === tab
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : intros.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center">
          <svg
            className="mx-auto h-12 w-12 text-slate-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
          <h3 className="mt-3 text-sm font-medium text-slate-900">
            No introductions sent yet
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Search candidates to get started.
          </p>
          <Link
            href="/employer/candidates"
            className="mt-4 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Search Candidates
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {intros.map((intro) => (
            <div
              key={intro.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-900">
                      {intro.candidate_name || "Unknown Candidate"}
                    </h3>
                    {statusBadge(intro.status)}
                  </div>
                  {intro.candidate_headline && (
                    <p className="mt-0.5 text-sm text-slate-600">
                      {intro.candidate_headline}
                    </p>
                  )}
                  {intro.job_title && (
                    <p className="mt-0.5 text-xs text-slate-400">
                      For: {intro.job_title}
                    </p>
                  )}
                  <p className="mt-2 text-sm text-slate-500 line-clamp-2">
                    {intro.message}
                  </p>
                </div>
                <div className="ml-4 flex-shrink-0 text-right text-xs text-slate-400">
                  {intro.created_at && (
                    <p>
                      Sent{" "}
                      {new Date(intro.created_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>

              {/* Accepted: reveal candidate email */}
              {intro.status === "accepted" && intro.candidate_email && (
                <div className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm">
                  <span className="text-green-700">Contact: </span>
                  <a
                    href={`mailto:${intro.candidate_email}`}
                    className="font-medium text-green-800 underline"
                  >
                    {intro.candidate_email}
                  </a>
                </div>
              )}

              {/* Candidate response message */}
              {intro.candidate_response_message && (
                <div className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  <span className="font-medium">Response:</span>{" "}
                  {intro.candidate_response_message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
