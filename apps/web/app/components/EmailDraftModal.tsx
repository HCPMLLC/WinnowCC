"use client";

import { useState, useEffect } from "react";
import UpgradeModal from "./UpgradeModal";
import { useUpgradeModal } from "../hooks/useUpgradeModal";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface EmailDraft {
  subject: string;
  greeting: string;
  body: string;
  closing: string;
  full_email: string;
}

interface Props {
  matchId: number;
  jobTitle: string;
  company: string;
  onClose: () => void;
}

export default function EmailDraftModal({
  matchId,
  jobTitle,
  company,
  onClose,
}: Props) {
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { modalProps: upgradeModalProps, handleBillingError, closeModal: closeUpgradeModal } = useUpgradeModal();

  useEffect(() => {
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/matches/${matchId}/draft-email`, {
          credentials: "include",
        });
        if (res.status === 403 || res.status === 429) {
          const handled = await handleBillingError(res, "Email Draft");
          if (handled) { setLoading(false); return; }
        }
        if (!res.ok) throw new Error("Failed to generate email draft");
        const data: EmailDraft = await res.json();
        setDraft(data);
      } catch {
        setError("Failed to generate email draft.");
      } finally {
        setLoading(false);
      }
    })();
  }, [matchId]);

  const copyToClipboard = () => {
    if (draft) {
      navigator.clipboard.writeText(draft.full_email);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const regenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/matches/${matchId}/draft-email`,
        { method: "POST", credentials: "include" },
      );
      if (res.status === 403 || res.status === 429) {
        const handled = await handleBillingError(res, "Email Draft");
        if (handled) return;
      }
      if (!res.ok) throw new Error("Failed to regenerate");
      const data: EmailDraft = await res.json();
      setDraft(data);
    } catch {
      setError("Failed to regenerate email draft.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Draft Application Email
            </h2>
            <p className="text-sm text-gray-500">
              {jobTitle} at {company}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {loading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-8 rounded bg-gray-200 w-2/3" />
            <div className="h-32 rounded bg-gray-200" />
          </div>
        ) : error ? (
          <p className="text-red-600 text-sm">{error}</p>
        ) : draft ? (
          <>
            {/* Subject */}
            <div className="mb-4">
              <label className="text-xs font-medium text-gray-500">
                Subject
              </label>
              <div className="rounded border border-gray-200 bg-gray-50 p-3 text-sm text-gray-900">
                {draft.subject}
              </div>
            </div>

            {/* Body */}
            <div className="mb-4">
              <label className="text-xs font-medium text-gray-500">
                Email
              </label>
              <div className="whitespace-pre-wrap rounded border border-gray-200 bg-gray-50 p-4 font-mono text-sm text-gray-900">
                {draft.greeting}
                {"\n\n"}
                {draft.body}
                {"\n\n"}
                {draft.closing}
                {"\n"}[Your Name]
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={copyToClipboard}
                className={`flex-1 rounded-lg py-2 font-medium ${
                  copied
                    ? "bg-green-100 text-green-700"
                    : "bg-emerald-600 text-white hover:bg-emerald-700"
                }`}
              >
                {copied ? "Copied!" : "Copy to Clipboard"}
              </button>
              <button
                onClick={regenerate}
                className="rounded-lg border border-gray-300 px-4 py-2 text-gray-600 hover:bg-gray-50"
              >
                Regenerate
              </button>
            </div>

            <p className="mt-4 text-center text-xs text-gray-400">
              Review and personalize before sending. Add your contact info and
              signature.
            </p>
          </>
        ) : null}

        <UpgradeModal {...upgradeModalProps} onClose={closeUpgradeModal} />
      </div>
    </div>
  );
}
