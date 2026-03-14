"use client";

import { useEffect, useState, useCallback } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface SelectedCandidate {
  id: number;
  name: string;
  match_score: number;
  type: "platform" | "pipeline";
}

interface ClientContact {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  role: string | null;
}

interface ClientOption {
  id: number;
  company_name: string;
  contacts: ClientContact[] | null;
}

interface SubmittalPackage {
  id: number;
  status: string;
  candidate_count: number;
  recipient_name: string;
  recipient_email: string;
  merged_pdf_url: string | null;
  cover_email_subject: string | null;
  cover_email_body: string | null;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

interface SubmittalModalProps {
  jobId: number;
  jobTitle: string;
  clientId: number | null;
  contactName: string | null;
  contactEmail: string | null;
  clients: ClientOption[];
  selectedCandidates: SelectedCandidate[];
  onClose: () => void;
  onPackageSent: () => void;
}

type ModalStep = "configure" | "building" | "ready" | "sent";

const inputCls =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

export default function SubmittalModal({
  jobId,
  jobTitle,
  clientId,
  contactName,
  contactEmail,
  clients,
  selectedCandidates,
  onClose,
  onPackageSent,
}: SubmittalModalProps) {
  const [step, setStep] = useState<ModalStep>("configure");
  const [candidates, setCandidates] = useState(selectedCandidates);
  const [recipientName, setRecipientName] = useState(contactName || "");
  const [recipientEmail, setRecipientEmail] = useState(contactEmail || "");
  const [selectedClientId, setSelectedClientId] = useState<number | null>(clientId);
  const [includeBriefs, setIncludeBriefs] = useState(true);
  const [includeResumes, setIncludeResumes] = useState(true);
  const [emailSubject, setEmailSubject] = useState(
    `Candidate Submittal \u2014 ${jobTitle}`
  );
  const [emailBody, setEmailBody] = useState(
    `Please find attached our candidate submittal package for ${jobTitle}.\n\nThis package includes candidate briefs and supporting documentation for your review.\n\nPlease don't hesitate to reach out with any questions.`
  );
  const [packageId, setPackageId] = useState<number | null>(null);
  const [packageData, setPackageData] = useState<SubmittalPackage | null>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  // Auto-fill from client contacts
  function handleClientChange(cId: string) {
    const id = cId ? Number(cId) : null;
    setSelectedClientId(id);
    if (id) {
      const client = clients.find((c) => c.id === id);
      if (client?.contacts?.length) {
        const ct = client.contacts[0];
        const name = [ct.first_name, ct.last_name].filter(Boolean).join(" ");
        if (name) setRecipientName(name);
        if (ct.email) setRecipientEmail(ct.email);
      }
    }
  }

  function removeCandidate(id: number) {
    setCandidates((prev) => prev.filter((c) => c.id !== id));
  }

  // Poll for package status
  const pollPackage = useCallback(async (pkgId: number) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/submittal-packages/${pkgId}`,
        { credentials: "include" }
      );
      if (!res.ok) return;
      const data: SubmittalPackage = await res.json();
      setPackageData(data);

      if (data.status === "ready") {
        setStep("ready");
      } else if (data.status === "sent") {
        setStep("sent");
      } else if (data.status === "failed") {
        setError(data.error_message || "Package build failed.");
        setStep("configure");
      }
      // If still building, keep polling
      return data.status;
    } catch {
      // Ignore polling errors
      return "building";
    }
  }, []);

  useEffect(() => {
    if (step !== "building" || !packageId) return;

    const interval = setInterval(async () => {
      const currentStatus = await pollPackage(packageId);
      if (currentStatus && currentStatus !== "building") {
        clearInterval(interval);
      }
    }, 3000);

    // Initial poll
    pollPackage(packageId);

    return () => clearInterval(interval);
  }, [step, packageId, pollPackage]);

  async function handleBuild() {
    setError("");

    if (!recipientName.trim() || !recipientEmail.trim()) {
      setError("Recipient name and email are required.");
      return;
    }
    if (candidates.length === 0) {
      setError("At least one candidate must be selected.");
      return;
    }

    try {
      const platformIds = candidates
        .filter((c) => c.type === "platform")
        .map((c) => c.id);
      const pipelineIds = candidates
        .filter((c) => c.type === "pipeline")
        .map((c) => c.id);

      const res = await fetch(
        `${API_BASE}/api/recruiter/jobs/${jobId}/submittal-package`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_ids: platformIds,
            pipeline_candidate_ids: pipelineIds,
            recipient_name: recipientName.trim(),
            recipient_email: recipientEmail.trim(),
            client_id: selectedClientId,
            options: {
              include_briefs: includeBriefs,
              include_resumes: includeResumes,
            },
            cover_email_subject: emailSubject,
            cover_email_body: `<p>${emailBody.replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>")}</p>`,
          }),
        }
      );

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Build failed" }));
        const detail = data.detail;
        if (typeof detail === "string") {
          setError(detail);
        } else if (Array.isArray(detail)) {
          setError(detail.map((e: { msg?: string }) => e.msg || "Validation error").join("; "));
        } else {
          setError("Failed to start package build.");
        }
        return;
      }

      const result = await res.json();
      setPackageId(result.package_id);
      setStep("building");
    } catch {
      setError("Network error. Please try again.");
    }
  }

  async function handleSend() {
    if (!packageId) return;
    setSending(true);
    setError("");

    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/submittal-packages/${packageId}/send`,
        { method: "POST", credentials: "include" }
      );

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Send failed" }));
        const detail = data.detail;
        if (typeof detail === "string") {
          setError(detail);
        } else if (Array.isArray(detail)) {
          setError(detail.map((e: { msg?: string }) => e.msg || "Validation error").join("; "));
        } else {
          setError("Failed to send package.");
        }
        return;
      }

      setStep("sent");
      onPackageSent();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-2xl rounded-xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {step === "configure" && "Build Submittal Package"}
            {step === "building" && "Building Package..."}
            {step === "ready" && "Package Ready"}
            {step === "sent" && "Package Sent"}
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[70vh] overflow-y-auto px-6 py-5">
          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* CONFIGURE STEP */}
          {step === "configure" && (
            <div className="space-y-5">
              {/* Selected candidates */}
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-700">
                  Selected Candidates ({candidates.length})
                </h3>
                <div className="space-y-2">
                  {candidates.map((c) => (
                    <div
                      key={`${c.type}-${c.id}`}
                      className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-slate-900">
                          {c.name}
                        </span>
                        <span className="text-xs text-slate-500">
                          {Math.round(c.match_score)}% match
                        </span>
                        {c.type === "pipeline" && (
                          <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                            Pipeline
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => removeCandidate(c.id)}
                        className="text-slate-400 hover:text-red-500"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recipient */}
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-700">
                  Send To
                </h3>
                {clients.length > 0 && (
                  <select
                    value={selectedClientId?.toString() || ""}
                    onChange={(e) => handleClientChange(e.target.value)}
                    className={`${inputCls} mb-2`}
                  >
                    <option value="">Select a client...</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.company_name}
                      </option>
                    ))}
                  </select>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs text-slate-500">
                      Recipient Name *
                    </label>
                    <input
                      type="text"
                      value={recipientName}
                      onChange={(e) => setRecipientName(e.target.value)}
                      className={inputCls}
                      placeholder="e.g. Jane Smith"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-500">
                      Recipient Email *
                    </label>
                    <input
                      type="email"
                      value={recipientEmail}
                      onChange={(e) => setRecipientEmail(e.target.value)}
                      className={inputCls}
                      placeholder="e.g. jane@company.com"
                    />
                  </div>
                </div>
              </div>

              {/* Package options */}
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-700">
                  Package Options
                </h3>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={includeBriefs}
                      onChange={(e) => setIncludeBriefs(e.target.checked)}
                      className="rounded border-slate-300"
                    />
                    Include AI Briefs
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={includeResumes}
                      onChange={(e) => setIncludeResumes(e.target.checked)}
                      className="rounded border-slate-300"
                    />
                    Include Resumes
                  </label>
                </div>
              </div>

              {/* Email preview */}
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-700">
                  Cover Email
                </h3>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">
                    Subject
                  </label>
                  <input
                    type="text"
                    value={emailSubject}
                    onChange={(e) => setEmailSubject(e.target.value)}
                    className={inputCls}
                  />
                </div>
                <div className="mt-2">
                  <label className="mb-1 block text-xs text-slate-500">
                    Body
                  </label>
                  <textarea
                    value={emailBody}
                    onChange={(e) => setEmailBody(e.target.value)}
                    rows={4}
                    className={inputCls}
                  />
                </div>
              </div>
            </div>
          )}

          {/* BUILDING STEP */}
          {step === "building" && (
            <div className="flex flex-col items-center py-10">
              <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-slate-700" />
              <p className="text-sm font-medium text-slate-900">
                Generating submittal package...
              </p>
              <p className="mt-1 text-xs text-slate-500">
                This may take a minute. AI briefs are being generated for each candidate.
              </p>
            </div>
          )}

          {/* READY STEP */}
          {step === "ready" && packageData && (
            <div className="space-y-5">
              <div className="flex flex-col items-center rounded-lg border border-emerald-200 bg-emerald-50 p-6">
                <svg className="mb-2 h-10 w-10 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm font-medium text-emerald-900">
                  Package built successfully!
                </p>
                <p className="mt-1 text-xs text-emerald-700">
                  {packageData.candidate_count} candidate{packageData.candidate_count !== 1 ? "s" : ""} included
                </p>
              </div>

              {packageData.merged_pdf_url && (
                <a
                  href={packageData.merged_pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 rounded-md border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Download PDF
                </a>
              )}

              <div className="rounded-lg border border-slate-200 p-4">
                <h4 className="mb-1 text-xs font-medium text-slate-500">
                  Will be sent to
                </h4>
                <p className="text-sm text-slate-900">
                  {packageData.recipient_name} &lt;{packageData.recipient_email}&gt;
                </p>
                {packageData.cover_email_subject && (
                  <>
                    <h4 className="mb-1 mt-3 text-xs font-medium text-slate-500">
                      Subject
                    </h4>
                    <p className="text-sm text-slate-700">
                      {packageData.cover_email_subject}
                    </p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* SENT STEP */}
          {step === "sent" && (
            <div className="flex flex-col items-center py-10">
              <svg className="mb-3 h-12 w-12 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 19v-8.93a2 2 0 01.89-1.664l7-4.666a2 2 0 012.22 0l7 4.666A2 2 0 0121 10.07V19M3 19a2 2 0 002 2h14a2 2 0 002-2M3 19l6.75-4.5M21 19l-6.75-4.5M3 10l6.75 4.5M21 10l-6.75 4.5m0 0l-1.14.76a2 2 0 01-2.22 0l-1.14-.76" />
              </svg>
              <p className="text-sm font-medium text-slate-900">
                Package sent successfully!
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Email delivered to {packageData?.recipient_name || recipientName}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-200 px-6 py-4">
          {step === "configure" && (
            <>
              <button
                onClick={onClose}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleBuild}
                disabled={candidates.length === 0}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                Build Package
              </button>
            </>
          )}

          {step === "building" && (
            <button
              onClick={onClose}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Close (build continues in background)
            </button>
          )}

          {step === "ready" && (
            <>
              <button
                onClick={onClose}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
              <button
                onClick={handleSend}
                disabled={sending}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {sending ? "Sending..." : "Send to Client"}
              </button>
            </>
          )}

          {step === "sent" && (
            <button
              onClick={onClose}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
