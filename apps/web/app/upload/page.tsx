"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";
import { useProgress } from "../hooks/useProgress";

type UploadResult = {
  resume_document_id: number;
  filename: string;
};

type ParseJobResult = {
  job_id: string;
  job_run_id: number;
  status: string;
};

type ParseJobStatus = {
  job_run_id: number;
  status: string;
  error_message?: string | null;
};

const MAX_UPLOAD_MB = 10;

export default function UploadPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const uploadProg = useProgress();
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<string | null>(null);
  const parseProg = useProgress();

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      setTimeout(resolve, ms);
    });

  useEffect(() => {
    const guard = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/login", redirectValue));
        return;
      }
      if (!me.onboarding_complete) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/onboarding", redirectValue));
      }
    };
    void guard();
  }, [pathname, router, searchParams]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setError("Please choose a PDF or DOCX file.");
      return;
    }

    uploadProg.start();
    setError(null);
    setResult(null);

    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(`${apiBase}/api/resume/upload`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        let message = "Upload failed. Please try again.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload?.detail) {
            message = payload.detail;
          }
        } catch {
          // Keep default message.
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as UploadResult;
      setResult(payload);
      setParseStatus(null);
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Upload failed.";
      setError(message);
    } finally {
      uploadProg.complete();
    }
  };

  const handleParse = async () => {
    if (!result) {
      return;
    }
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
    parseProg.start();
    setParseStatus(null);
    setError(null);

    try {
      const response = await fetch(
        `${apiBase}/api/resume/${result.resume_document_id}/parse`,
        { method: "POST", credentials: "include" }
      );
      if (!response.ok) {
        let message = "Failed to start parsing.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload?.detail) {
            message = payload.detail;
          }
        } catch {
          // Keep default message.
        }
        throw new Error(message);
      }
      const payload = (await response.json()) as ParseJobResult;
      setParseStatus("Parse queued. Waiting for completion...");

      const maxTries = 20;
      for (let i = 0; i < maxTries; i += 1) {
        await sleep(1000);
        const statusResponse = await fetch(
          `${apiBase}/api/resume/parse/${payload.job_run_id}`,
          { credentials: "include" }
        );
        if (!statusResponse.ok) {
          throw new Error("Failed to fetch parse status.");
        }
        const statusPayload = (await statusResponse.json()) as ParseJobStatus;
        if (statusPayload.status === "succeeded") {
          setParseStatus("Parse complete. Visit your profile to review.");
          return;
        }
        if (statusPayload.status === "failed") {
          throw new Error(
            statusPayload.error_message || "Parse failed. Please retry."
          );
        }
        setParseStatus(`Parsing... (${i + 1}/${maxTries})`);
      }

      setParseStatus("Parsing is taking longer than expected. Check back soon.");
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to start parsing.";
      setError(message);
    } finally {
      parseProg.complete();
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-16">
      <header>
        <h1 className="text-3xl font-semibold">Upload Resume</h1>
        <p className="mt-2 text-sm text-slate-600">
          Upload a PDF or DOCX. Maximum size is {MAX_UPLOAD_MB}MB.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
          Resume file
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={(event) =>
              setSelectedFile(event.target.files?.[0] ?? null)
            }
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
          />
        </label>

        <button
          type="submit"
          disabled={uploadProg.isActive}
          className="relative overflow-hidden rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed"
        >
          {uploadProg.isActive && (
            <span
              className="absolute inset-y-0 left-0 bg-slate-700 transition-all duration-200"
              style={{ width: `${uploadProg.progress}%` }}
            />
          )}
          <span className="relative">
            {uploadProg.isActive
              ? `Uploading... ${uploadProg.pct}%`
              : "Upload resume"}
          </span>
        </button>
      </form>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="flex flex-col gap-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div>
            Upload complete. ID {result.resume_document_id}, file{" "}
            {result.filename}.
          </div>
          <button
            type="button"
            onClick={handleParse}
            disabled={parseProg.isActive}
            className="relative w-fit overflow-hidden rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed"
          >
            {parseProg.isActive && (
              <span
                className="absolute inset-y-0 left-0 bg-emerald-600 transition-all duration-200"
                style={{ width: `${parseProg.progress}%` }}
              />
            )}
            <span className="relative">
              {parseProg.isActive
                ? `Building profile... ${parseProg.pct}%`
                : "Build my profile"}
            </span>
          </button>
          {parseStatus ? (
            <div className="text-sm text-emerald-900">{parseStatus}</div>
          ) : null}
        </div>
      ) : null}
    </main>
  );
}
