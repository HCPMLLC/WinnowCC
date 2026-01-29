"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";

type Job = {
  id: number;
  company: string;
  url: string;
  title: string;
  description_text: string;
  location: string;
  application_deadline: string | null;
  hiring_manager_name: string | null;
  hiring_manager_email: string | null;
  hiring_manager_phone: string | null;
};

type Match = {
  id: number;
  job: Job;
  match_score: number;
  interview_readiness_score: number;
  offer_probability: number;
  reasons: Record<string, unknown>;
};

type TailorStatus = {
  status: string;
  resume_url?: string | null;
  cover_letter_url?: string | null;
  error_message?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function MatchesPage() {
  const router = useRouter();
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [statusByJob, setStatusByJob] = useState<Record<number, string>>({});
  const [linksByJob, setLinksByJob] = useState<
    Record<number, { resume?: string; cover?: string }>
  >({});
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);

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

  useEffect(() => {
    const loadMatches = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/matches`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load matches.");
        }
        const payload = (await response.json()) as Match[];
        setMatches(payload);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load matches.";
        setError(message);
      }
    };
    void loadMatches();
  }, []);

  const toggleExpand = (matchId: number) => {
    setExpanded((current) => ({ ...current, [matchId]: !current[matchId] }));
  };

  const handlePrepare = async (jobId: number) => {
    setStatusByJob((current) => ({ ...current, [jobId]: "Queued..." }));
    setLinksByJob((current) => ({ ...current, [jobId]: {} }));

    try {
      const response = await fetch(`${API_BASE}/api/tailor/${jobId}`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to start tailoring.");
      }
      const payload = (await response.json()) as { job_id: string };

      const maxTries = 20;
      for (let i = 0; i < maxTries; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const statusResponse = await fetch(
          `${API_BASE}/api/tailor/status/${payload.job_id}`,
          { credentials: "include" }
        );
        if (!statusResponse.ok) {
          throw new Error("Failed to fetch tailoring status.");
        }
        const statusPayload = (await statusResponse.json()) as TailorStatus;
        if (statusPayload.status === "finished") {
          setStatusByJob((current) => ({
            ...current,
            [jobId]: "Ready",
          }));
          setLinksByJob((current) => ({
            ...current,
            [jobId]: {
              resume: statusPayload.resume_url ?? undefined,
              cover: statusPayload.cover_letter_url ?? undefined,
            },
          }));
          return;
        }
        if (statusPayload.status === "failed") {
          throw new Error(statusPayload.error_message || "Tailoring failed.");
        }
        setStatusByJob((current) => ({
          ...current,
          [jobId]: `Working... (${i + 1}/${maxTries})`,
        }));
      }
      setStatusByJob((current) => ({
        ...current,
        [jobId]: "Still processing. Check back soon.",
      }));
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Tailoring failed.";
      setStatusByJob((current) => ({ ...current, [jobId]: message }));
    }
  };

  const handleRefresh = async () => {
    setRefreshStatus("Refreshing matches...");
    try {
      const response = await fetch(`${API_BASE}/api/matches/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to refresh matches.");
      }
      setRefreshStatus("Refresh queued. Reload in a moment.");
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to refresh matches.";
      setRefreshStatus(message);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Top Matches</h1>
        <p className="text-sm text-slate-600">
          The top 5 jobs most aligned with your profile.
        </p>
        <div className="mt-2 flex items-center gap-4">
          <button
            type="button"
            onClick={handleRefresh}
            className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
          >
            Refresh matches
          </button>
          {refreshStatus ? (
            <span className="text-xs text-slate-500">{refreshStatus}</span>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Job Title</th>
              <th className="px-4 py-3">Location</th>
              <th className="px-4 py-3">Deadline</th>
              <th className="px-4 py-3">Hiring Manager</th>
              <th className="px-4 py-3">Contact</th>
              <th className="px-4 py-3">Prepare</th>
            </tr>
          </thead>
          <tbody>
            {matches.map((match) => {
              const job = match.job;
              const shortDescription = job.description_text.slice(0, 140);
              const isExpanded = expanded[match.id];
              const statusText = statusByJob[job.id];
              const links = linksByJob[job.id] || {};
              return (
                <tr key={match.id} className="border-b border-slate-100">
                  <td className="px-4 py-4 font-medium text-slate-900">
                    {job.company}
                    <div className="text-xs text-slate-500">
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
                      >
                        Job posting
                      </a>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="font-semibold text-slate-900">
                      {job.title}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Match {match.match_score} | Interview{" "}
                      {match.interview_readiness_score} | Offer{" "}
                      {match.offer_probability}
                    </div>
                    <button
                      type="button"
                      className="mt-2 text-xs text-slate-700 underline"
                      onClick={() => toggleExpand(match.id)}
                    >
                      {isExpanded ? "Hide description" : "Show description"}
                    </button>
                    <p className="mt-2 text-xs text-slate-600">
                      {isExpanded ? job.description_text : `${shortDescription}...`}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-slate-700">{job.location}</td>
                  <td className="px-4 py-4 text-slate-700">
                    {job.application_deadline
                      ? new Date(job.application_deadline).toLocaleDateString()
                      : "N/A"}
                  </td>
                  <td className="px-4 py-4 text-slate-700">
                    {job.hiring_manager_name || "N/A"}
                  </td>
                  <td className="px-4 py-4 text-slate-700">
                    <div>{job.hiring_manager_email || "N/A"}</div>
                    <div>{job.hiring_manager_phone || ""}</div>
                  </td>
                  <td className="px-4 py-4">
                    <button
                      type="button"
                      onClick={() => handlePrepare(job.id)}
                      className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
                    >
                      Prepare
                    </button>
                    {statusText ? (
                      <div className="mt-2 text-xs text-slate-600">
                        {statusText}
                      </div>
                    ) : null}
                    {links.resume || links.cover ? (
                      <div className="mt-2 flex flex-col gap-1 text-xs text-slate-700">
                        {links.resume ? (
                          <a className="underline" href={links.resume}>
                            Download resume
                          </a>
                        ) : null}
                        {links.cover ? (
                          <a className="underline" href={links.cover}>
                            Download cover letter
                          </a>
                        ) : null}
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {matches.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-sm text-slate-500" colSpan={7}>
                  No matches yet. Refresh matches after job ingestion.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
