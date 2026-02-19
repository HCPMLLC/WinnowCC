"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import JobForm, { type JobFormData } from "../../_components/JobForm";
import Spinner from "../../../../components/Spinner";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function EditJobPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = Number(params.id);

  const [initialData, setInitialData] = useState<Partial<JobFormData> | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [parsedFromDocument, setParsedFromDocument] = useState(false);
  const [parsingConfidence, setParsingConfidence] = useState<number | null>(
    null,
  );
  const [isReparsing, setIsReparsing] = useState(false);
  const [reparseMessage, setReparseMessage] = useState<string | null>(null);

  useEffect(() => {
    async function fetchJob() {
      try {
        const res = await fetch(`${API_BASE}/api/employer/jobs/${jobId}`, {
          credentials: "include",
        });
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || "Job not found");
        }
        const job = await res.json();

        setParsedFromDocument(job.parsed_from_document ?? false);
        setParsingConfidence(job.parsing_confidence ?? null);

        setInitialData({
          title: job.title ?? "",
          description: job.description ?? "",
          requirements: job.requirements ?? "",
          nice_to_haves: job.nice_to_haves ?? "",
          location: job.location ?? "",
          remote_policy: job.remote_policy ?? "",
          employment_type: job.employment_type ?? "",
          salary_min: job.salary_min != null ? String(job.salary_min) : "",
          salary_max: job.salary_max != null ? String(job.salary_max) : "",
          salary_currency: job.salary_currency ?? "USD",
          equity_offered: job.equity_offered ?? false,
          application_email: job.application_email ?? "",
          application_url: job.application_url ?? "",
          job_id_external: job.job_id_external ?? "",
          start_date: job.start_date ? job.start_date.split("T")[0] : "",
          close_date: job.close_date ? job.close_date.split("T")[0] : "",
          job_category: job.job_category ?? "",
          department: job.department ?? "",
          certifications_required: job.certifications_required ?? [],
          job_type: job.job_type ?? "",
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
      } finally {
        setIsLoading(false);
      }
    }
    fetchJob();
  }, [jobId]);

  async function handleReparse(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsReparsing(true);
    setReparseMessage(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/${jobId}/reparse-document`,
        { method: "POST", credentials: "include", body: formData },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Re-parse failed");
      }
      const job = await res.json();
      setInitialData({
        title: job.title ?? "",
        description: job.description ?? "",
        requirements: job.requirements ?? "",
        nice_to_haves: job.nice_to_haves ?? "",
        location: job.location ?? "",
        remote_policy: job.remote_policy ?? "",
        employment_type: job.employment_type ?? "",
        salary_min: job.salary_min != null ? String(job.salary_min) : "",
        salary_max: job.salary_max != null ? String(job.salary_max) : "",
        salary_currency: job.salary_currency ?? "USD",
        equity_offered: job.equity_offered ?? false,
        application_email: job.application_email ?? "",
        application_url: job.application_url ?? "",
        job_id_external: job.job_id_external ?? "",
        start_date: job.start_date ? job.start_date.split("T")[0] : "",
        close_date: job.close_date ? job.close_date.split("T")[0] : "",
        job_category: job.job_category ?? "",
        department: job.department ?? "",
        certifications_required: job.certifications_required ?? [],
        job_type: job.job_type ?? "",
      });
      setParsingConfidence(job.parsing_confidence ?? null);
      setReparseMessage("Document re-parsed. Review the updated fields below.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-parse failed");
    } finally {
      setIsReparsing(false);
      e.target.value = "";
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
        <div className="h-96 animate-pulse rounded-xl border border-slate-200 bg-white" />
      </div>
    );
  }

  if (error || !initialData) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "Failed to load job data"}
        </div>
        <Link
          href={`/employer/jobs/${jobId}`}
          className="mt-4 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          &larr; Back to Job
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <Link
          href={`/employer/jobs/${jobId}`}
          className="mb-2 inline-block text-sm text-slate-500 hover:text-slate-700"
        >
          &larr; Back to Job
        </Link>
        <h1 className="text-3xl font-bold text-slate-900">
          Edit Job Posting
        </h1>
        <p className="mt-1 text-slate-600">
          Update job details and save your changes
        </p>
      </div>

      {parsedFromDocument && (
        <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          <div className="flex items-center justify-between">
            <span>
              Parsed from uploaded document
              {parsingConfidence != null &&
                ` (${(parsingConfidence * 100).toFixed(0)}% confidence)`}
              . Please review and correct all fields before publishing.
            </span>
            <label className="ml-4 inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-md border border-blue-300 bg-white px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50">
              {isReparsing ? <><Spinner className="h-3 w-3" /> Re-parsing...</> : "Re-parse Document"}
              <input
                type="file"
                accept=".doc,.docx,.pdf,.txt"
                onChange={handleReparse}
                disabled={isReparsing}
                className="hidden"
              />
            </label>
          </div>
        </div>
      )}

      {reparseMessage && (
        <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          {reparseMessage}
        </div>
      )}

      <JobForm
        mode="edit"
        jobId={jobId}
        initialData={initialData}
        onSuccess={() => router.push(`/employer/jobs/${jobId}`)}
        onCancel={() => router.push(`/employer/jobs/${jobId}`)}
      />
    </div>
  );
}
