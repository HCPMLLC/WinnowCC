"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface IntroRequest {
  id: number;
  recruiter_profile_id: number;
  candidate_profile_id: number;
  recruiter_job_id: number | null;
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
  job_client: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  accepted: "bg-emerald-100 text-emerald-700",
  declined: "bg-red-100 text-red-700",
  expired: "bg-slate-100 text-slate-500",
};

const TABS = ["all", "pending", "accepted", "declined", "expired"];

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function expiresIn(dateStr: string | null): string | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  if (diff <= 0) return "Expired";
  const days = Math.ceil(diff / 86400000);
  return `${days}d left`;
}

export default function RecruiterIntroductionsPage() {
  const [intros, setIntros] = useState<IntroRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");

  useEffect(() => {
    setLoading(true);
    const url = new URL(`${API_BASE}/api/recruiter/introductions`);
    if (activeTab !== "all") url.searchParams.set("status", activeTab);
    url.searchParams.set("limit", "100");

    fetch(url.toString(), { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setIntros(Array.isArray(data) ? data : []))
      .finally(() => setLoading(false));
  }, [activeTab]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Introductions</h1>
        <p className="mt-1 text-sm text-slate-500">
          Track your introduction requests and connect with candidates
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
              activeTab === tab
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-12 text-center text-sm text-slate-500">Loading...</div>
      ) : intros.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <p className="text-slate-500">
            {activeTab === "all"
              ? "No introduction requests yet. Request introductions from candidate profiles or your pipeline."
              : `No ${activeTab} introduction requests.`}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {intros.map((intro) => (
            <div
              key={intro.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-base font-semibold text-slate-900">
                      {intro.candidate_name || `Candidate #${intro.candidate_profile_id}`}
                    </h3>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                        STATUS_COLORS[intro.status] || "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {intro.status}
                    </span>
                  </div>

                  {intro.candidate_headline && (
                    <p className="mt-0.5 text-sm text-slate-600">{intro.candidate_headline}</p>
                  )}
                  {intro.candidate_location && (
                    <p className="mt-0.5 text-sm text-slate-500">{intro.candidate_location}</p>
                  )}

                  {intro.job_title && (
                    <p className="mt-1 text-xs text-slate-500">
                      Job:{" "}
                      {intro.recruiter_job_id ? (
                        <Link
                          href={`/recruiter/jobs/${intro.recruiter_job_id}`}
                          className="font-medium text-blue-600 hover:underline"
                        >
                          {intro.job_title}
                        </Link>
                      ) : (
                        <span className="font-medium text-slate-700">{intro.job_title}</span>
                      )}
                      {intro.job_client && ` at ${intro.job_client}`}
                    </p>
                  )}

                  <p className="mt-2 text-sm text-slate-600 line-clamp-2">{intro.message}</p>

                  {intro.candidate_response_message && (
                    <div className="mt-2 rounded-md bg-slate-50 px-3 py-2">
                      <p className="text-xs font-medium text-slate-500">Candidate response:</p>
                      <p className="text-sm text-slate-700">{intro.candidate_response_message}</p>
                    </div>
                  )}

                  {/* Revealed contact info on acceptance */}
                  {intro.status === "accepted" && intro.candidate_email && (
                    <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                        Contact Information Revealed
                      </p>
                      {intro.candidate_name && (
                        <p className="mt-1 text-sm text-emerald-900">
                          <span className="font-medium">Name:</span> {intro.candidate_name}
                        </p>
                      )}
                      <p className="text-sm text-emerald-900">
                        <span className="font-medium">Email:</span>{" "}
                        <a
                          href={`mailto:${intro.candidate_email}`}
                          className="underline hover:text-emerald-700"
                        >
                          {intro.candidate_email}
                        </a>
                      </p>
                    </div>
                  )}
                </div>

                <div className="shrink-0 text-right text-xs text-slate-400">
                  <div>{timeAgo(intro.created_at)}</div>
                  {intro.status === "pending" && intro.expires_at && (
                    <div className="mt-1 text-amber-500">
                      {expiresIn(intro.expires_at)}
                    </div>
                  )}
                  {intro.responded_at && (
                    <div className="mt-1">
                      Responded {timeAgo(intro.responded_at)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
