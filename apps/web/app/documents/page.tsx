"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { fetchAuthMe } from "../lib/auth";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type DocumentItem = {
  id: number;
  job_id: number;
  job_title: string | null;
  company: string | null;
  profile_version: number;
  has_resume: boolean;
  has_cover_letter: boolean;
  created_at: string | null;
};

export default function DocumentsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const guard = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        router.replace("/login");
        return;
      }
    };
    void guard();
  }, [router]);

  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/tailor/documents`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error("Failed to load documents.");
        const data = await res.json();
        setDocuments(data.documents ?? []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load documents.",
        );
      } finally {
        setLoading(false);
      }
    };
    void fetchDocuments();
  }, []);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <CandidateLayout>
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Documents</h1>
        <p className="mt-1 text-sm text-slate-600">
          Your tailored resumes and cover letters, generated for each job match.
        </p>
      </header>

      <div className="mb-6">
        <CollapsibleTip title="Your Documents" defaultOpen={false}>
          <p>
            Tailored resumes and cover letters are generated when you click
            &quot;Prepare Materials&quot; on a match. Each is customized for the
            specific job posting to maximize your interview probability.
          </p>
        </CollapsibleTip>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="mb-2 h-4 w-48 rounded bg-slate-200" />
              <div className="h-3 w-32 rounded bg-slate-200" />
            </div>
          ))}
        </div>
      )}

      {!loading && documents.length === 0 && !error && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
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
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
          <h3 className="mt-4 text-lg font-semibold text-slate-900">
            No documents yet
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            Go to your matches and click &quot;Prepare Materials&quot; on any
            job to generate a tailored resume and cover letter.
          </p>
          <Link
            href="/matches"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Browse Matches
          </Link>
        </div>
      )}

      {!loading && documents.length > 0 && (
        <div className="space-y-3">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-semibold text-slate-900">
                  {doc.job_title ?? "Unknown Job"}
                </h3>
                <p className="mt-0.5 text-sm text-slate-600">
                  {doc.company ?? "Unknown Company"}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Generated {formatDate(doc.created_at)}
                </p>
              </div>

              <div className="ml-4 flex shrink-0 items-center gap-2">
                {doc.has_resume && (
                  <a
                    href={`${API_BASE}/api/tailor/files/${doc.id}/resume`}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
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
                        d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    Resume
                  </a>
                )}
                {doc.has_cover_letter && (
                  <a
                    href={`${API_BASE}/api/tailor/files/${doc.id}/cover-letter`}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
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
                        d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    Cover Letter
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </CandidateLayout>
  );
}
