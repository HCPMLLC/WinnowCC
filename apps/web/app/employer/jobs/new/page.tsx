"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import JobForm from "../_components/JobForm";
import Spinner from "../../../components/Spinner";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface BulkFileResult {
  filename: string;
  success: boolean;
  job_id: number | null;
  title: string | null;
  error: string | null;
}

interface BulkUploadResponse {
  results: BulkFileResult[];
  total_submitted: number;
  total_succeeded: number;
  total_failed: number;
  upgrade_recommendation: string | null;
}

export default function CreateJobPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"manual" | "upload" | "bulk">("manual");
  const [error, setError] = useState("");

  // Single upload state
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Bulk upload state
  const [bulkFiles, setBulkFiles] = useState<File[]>([]);
  const [isBulkUploading, setIsBulkUploading] = useState(false);
  const [bulkResults, setBulkResults] = useState<BulkUploadResponse | null>(
    null,
  );

  async function handleUpload() {
    if (!file) return;
    setIsUploading(true);
    setError("");

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(
        `${API_BASE}/api/employer/jobs/upload-document`,
        {
          method: "POST",
          credentials: "include",
          body: fd,
        },
      );

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Upload failed");
      }

      const data = await res.json();
      router.push(`/employer/jobs/${data.job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleBulkUpload() {
    if (bulkFiles.length === 0) return;
    setIsBulkUploading(true);
    setError("");
    setBulkResults(null);

    try {
      const fd = new FormData();
      for (const f of bulkFiles) {
        fd.append("files", f);
      }

      const res = await fetch(
        `${API_BASE}/api/employer/jobs/upload-documents`,
        {
          method: "POST",
          credentials: "include",
          body: fd,
        },
      );

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Bulk upload failed");
      }

      const data: BulkUploadResponse = await res.json();
      setBulkResults(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Bulk upload failed");
    } finally {
      setIsBulkUploading(false);
    }
  }

  function handleBulkFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files;
    if (selected) {
      setBulkFiles(Array.from(selected));
      setBulkResults(null);
    }
  }

  function removeBulkFile(index: number) {
    setBulkFiles((prev) => prev.filter((_, i) => i !== index));
    setBulkResults(null);
  }

  const modes = [
    { key: "manual" as const, label: "Manual Entry" },
    { key: "upload" as const, label: "Upload Document" },
    { key: "bulk" as const, label: "Bulk Upload" },
  ];

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">
          Create Job Posting
        </h1>
        <p className="mt-1 text-slate-600">
          Fill in the details, upload a document, or bulk upload multiple files
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="mb-6 flex gap-4">
        {modes.map((m) => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`flex-1 rounded-lg py-3 px-4 font-medium transition-colors ${
              mode === m.key
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {mode === "bulk" ? (
        /* ============ BULK UPLOAD MODE ============ */
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">
            Bulk Upload Job Descriptions
          </h3>
          <p className="text-sm text-slate-600">
            Upload multiple job description files at once. Each file will be
            parsed and a draft job posting created for your review.
          </p>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Choose Files (.doc, .docx, .pdf, .txt)
            </label>
            <input
              type="file"
              multiple
              accept=".doc,.docx,.pdf,.txt"
              onChange={handleBulkFileChange}
              className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-md file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-200"
            />
          </div>

          {/* File list preview */}
          {bulkFiles.length > 0 && !bulkResults && (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="mb-2 text-sm font-medium text-slate-700">
                {bulkFiles.length} file(s) selected
              </p>
              <ul className="space-y-1">
                {bulkFiles.map((f, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between text-sm text-slate-600"
                  >
                    <span className="truncate">{f.name}</span>
                    <button
                      onClick={() => removeBulkFile(i)}
                      className="ml-2 text-red-500 hover:text-red-700"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!bulkResults && (
            <button
              onClick={handleBulkUpload}
              disabled={bulkFiles.length === 0 || isBulkUploading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isBulkUploading
                ? <><Spinner /> Parsing {bulkFiles.length} file(s)...</>
                : `Upload & Parse ${bulkFiles.length} File(s)`}
            </button>
          )}

          {/* Results table */}
          {bulkResults && (
            <div className="space-y-3">
              <div className="flex gap-4 text-sm">
                <span className="text-slate-600">
                  Submitted: {bulkResults.total_submitted}
                </span>
                <span className="text-green-700">
                  Succeeded: {bulkResults.total_succeeded}
                </span>
                {bulkResults.total_failed > 0 && (
                  <span className="text-red-700">
                    Failed: {bulkResults.total_failed}
                  </span>
                )}
              </div>

              {bulkResults.upgrade_recommendation && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  {bulkResults.upgrade_recommendation}
                </div>
              )}

              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-600">
                    <th className="pb-2 font-medium">File</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Title</th>
                    <th className="pb-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {bulkResults.results.map((r, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-2 pr-2 truncate max-w-[180px]">
                        {r.filename}
                      </td>
                      <td className="py-2 pr-2">
                        {r.success ? (
                          <span className="text-green-600">Success</span>
                        ) : (
                          <span
                            className="text-red-600 cursor-help"
                            title={r.error || ""}
                          >
                            Failed
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-2 truncate max-w-[180px]">
                        {r.title || (r.error ? r.error : "-")}
                      </td>
                      <td className="py-2">
                        {r.success && r.job_id && (
                          <button
                            onClick={() =>
                              router.push(`/employer/jobs/${r.job_id}`)
                            }
                            className="text-blue-600 hover:underline"
                          >
                            View
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <button
                onClick={() => {
                  setBulkResults(null);
                  setBulkFiles([]);
                }}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
              >
                Upload More
              </button>
            </div>
          )}

          <div className="text-xs text-slate-500">
            <p className="mb-1 font-medium">Supported:</p>
            <ul className="list-inside list-disc space-y-0.5">
              <li>.doc, .docx, .pdf, .txt files up to 10 MB each</li>
              <li>Batch limits depend on your subscription tier</li>
              <li>Creates draft postings for review before publishing</li>
            </ul>
          </div>
        </div>
      ) : mode === "upload" ? (
        /* ============ UPLOAD MODE ============ */
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">
            Upload Job Description Document
          </h3>
          <p className="text-sm text-slate-600">
            Upload a job description document. We&apos;ll automatically extract
            the details using AI and create a draft for your review.
          </p>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Choose Document (.doc, .docx, .pdf)
            </label>
            <input
              type="file"
              accept=".doc,.docx,.pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-md file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-200"
            />
          </div>

          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isUploading ? <><Spinner /> Parsing document...</> : "Upload & Parse"}
          </button>

          <div className="text-xs text-slate-500">
            <p className="mb-1 font-medium">Supported:</p>
            <ul className="list-inside list-disc space-y-0.5">
              <li>.doc, .docx, .pdf files up to 10 MB</li>
              <li>
                Extracts: title, description, requirements, dates, salary, etc.
              </li>
              <li>Creates a draft for you to review before publishing</li>
            </ul>
          </div>
        </div>
      ) : (
        /* ============ MANUAL FORM ============ */
        <JobForm
          mode="create"
          onSuccess={(job) => router.push(`/employer/jobs/${job.id}`)}
          onCancel={() => router.back()}
        />
      )}
    </div>
  );
}
