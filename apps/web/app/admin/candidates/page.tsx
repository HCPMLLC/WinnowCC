"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type Candidate = {
  user_id: number;
  full_name: string | null;
  first_name: string | null;
  last_name: string | null;
  title: string | null;
  city: string | null;
  state: string | null;
  location: string | null;
  work_authorization: string | null;
  years_experience: number | null;
  email: string | null;
  phone: string | null;
  date_added: string | null;
  date_modified: string | null;
  trust_status: string | null;
  match_count: number;
  resume_document_id: number | null;
  resume_filename: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// Format date as MM/DD/YYYY
const formatDate = (isoString: string | null): string => {
  if (!isoString) return "—";
  const date = new Date(isoString);
  return date.toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
};

// Trust status badge
const TrustBadge = ({ status }: { status: string | null }) => {
  if (!status) return <span className="text-slate-400">—</span>;

  const colors: Record<string, string> = {
    allowed: "bg-emerald-100 text-emerald-700 border-emerald-200",
    soft_quarantine: "bg-amber-100 text-amber-700 border-amber-200",
    hard_quarantine: "bg-red-100 text-red-700 border-red-200",
  };

  const labels: Record<string, string> = {
    allowed: "Allowed",
    soft_quarantine: "Soft Q",
    hard_quarantine: "Hard Q",
  };

  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colors[status] || "bg-slate-100 text-slate-600"}`}
    >
      {labels[status] || status}
    </span>
  );
};

export default function AdminCandidatesPage() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [primaryUserId, setPrimaryUserId] = useState<number | null>(null);
  const [previewResumeId, setPreviewResumeId] = useState<number | null>(null);
  const [previewFilename, setPreviewFilename] = useState<string | null>(null);
  const [docxHtml, setDocxHtml] = useState<string | null>(null);
  const [docxLoading, setDocxLoading] = useState(false);

  // Load and convert .docx file when preview modal opens
  const loadDocxPreview = useCallback(async (resumeId: number) => {
    setDocxLoading(true);
    setDocxHtml(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/candidates/resume/${resumeId}`,
        { credentials: "include" }
      );
      if (!response.ok) {
        throw new Error("Failed to load document");
      }
      const arrayBuffer = await response.arrayBuffer();
      const mammoth = (await import("mammoth")).default;
      const result = await mammoth.convertToHtml({ arrayBuffer });
      setDocxHtml(result.value);
    } catch (err) {
      console.error("Failed to convert docx:", err);
      setDocxHtml(null);
    } finally {
      setDocxLoading(false);
    }
  }, []);

  // Trigger docx conversion when preview opens for a .docx file
  useEffect(() => {
    if (
      previewResumeId &&
      previewFilename?.toLowerCase().endsWith(".docx")
    ) {
      loadDocxPreview(previewResumeId);
    } else {
      setDocxHtml(null);
    }
  }, [previewResumeId, previewFilename, loadDocxPreview]);

  const loadCandidates = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/candidates`, {
        credentials: "include",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 403) {
        setError("Admin access required.");
        setIsLoading(false);
        return;
      }
      if (!response.ok) {
        throw new Error("Failed to load candidates.");
      }
      const payload = (await response.json()) as Candidate[];
      setCandidates(payload);
      setSelectedIds(new Set());
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to load candidates.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadCandidates();
  }, [loadCandidates]);

  // Filter candidates by search term
  const filteredCandidates = candidates.filter((c) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      c.full_name?.toLowerCase().includes(term) ||
      c.email?.toLowerCase().includes(term) ||
      c.title?.toLowerCase().includes(term) ||
      c.city?.toLowerCase().includes(term) ||
      c.state?.toLowerCase().includes(term)
    );
  });

  // Selection handlers
  const toggleSelect = (userId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredCandidates.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredCandidates.map((c) => c.user_id)));
    }
  };

  // Delete selected candidates
  const handleDelete = async () => {
    if (selectedIds.size === 0) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete ${selectedIds.size} candidate(s)? This action cannot be undone.`
    );
    if (!confirmed) return;

    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(`${API_BASE}/api/admin/candidates/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user_ids: Array.from(selectedIds) }),
      });

      if (!response.ok) {
        throw new Error("Failed to delete candidates.");
      }

      const result = (await response.json()) as { message: string };
      setSuccessMessage(result.message);
      await loadCandidates();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to delete candidates.";
      setError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  // Merge duplicates
  const handleMerge = async () => {
    if (selectedIds.size < 2 || !primaryUserId) return;

    const duplicateIds = Array.from(selectedIds).filter(
      (id) => id !== primaryUserId
    );

    setIsMerging(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(`${API_BASE}/api/admin/candidates/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          primary_user_id: primaryUserId,
          duplicate_user_ids: duplicateIds,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to merge candidates.");
      }

      const result = (await response.json()) as { message: string };
      setSuccessMessage(result.message);
      setShowMergeModal(false);
      setPrimaryUserId(null);
      await loadCandidates();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to merge candidates.";
      setError(message);
    } finally {
      setIsMerging(false);
    }
  };

  // Find potential duplicates (same email)
  const duplicateEmails = candidates.reduce(
    (acc, c) => {
      if (c.email) {
        acc[c.email] = (acc[c.email] || 0) + 1;
      }
      return acc;
    },
    {} as Record<string, number>
  );
  const hasDuplicates = Object.values(duplicateEmails).some((count) => count > 1);

  if (isLoading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
        <h1 className="text-3xl font-semibold">Candidates</h1>
        <p className="text-sm text-slate-600">Loading candidates...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">All Candidates</h1>
        <p className="text-sm text-slate-600">
          {candidates.length} total candidates
          {hasDuplicates && (
            <span className="ml-2 text-amber-600">
              (Potential duplicates detected)
            </span>
          )}
        </p>
      </header>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {successMessage}
        </div>
      )}

      {/* Search and Actions */}
      <div className="flex flex-wrap items-center gap-4">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by name, email, title, city, or state..."
          className="w-full max-w-md rounded-xl border border-slate-200 px-4 py-2 text-sm"
        />
        {searchTerm && (
          <span className="text-sm text-slate-500">
            {filteredCandidates.length} results
          </span>
        )}

        <div className="ml-auto flex gap-2">
          {selectedIds.size >= 2 && (
            <button
              type="button"
              onClick={() => {
                setPrimaryUserId(Array.from(selectedIds)[0]);
                setShowMergeModal(true);
              }}
              className="rounded-full bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
            >
              Merge Selected ({selectedIds.size})
            </button>
          )}
          {selectedIds.size > 0 && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className="rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
            >
              {isDeleting ? "Deleting..." : `Delete Selected (${selectedIds.size})`}
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="sticky left-0 z-20 bg-slate-50 px-4 py-3">
                <input
                  type="checkbox"
                  checked={
                    filteredCandidates.length > 0 &&
                    selectedIds.size === filteredCandidates.length
                  }
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-slate-300"
                />
              </th>
              <th className="sticky left-[52px] z-20 whitespace-nowrap border-r border-slate-200 bg-slate-50 px-4 py-3 font-semibold text-slate-700">
                Full Name
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Title
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                City
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                State
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Work Auth
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Yrs Exp
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Email
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Phone
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Trust
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Resume
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Date Added
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Last Modified
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Matches
              </th>
              <th className="whitespace-nowrap px-4 py-3 font-semibold text-slate-700">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredCandidates.length === 0 ? (
              <tr>
                <td colSpan={15} className="px-4 py-8 text-center text-slate-500">
                  {searchTerm
                    ? "No candidates match your search."
                    : "No candidates found."}
                </td>
              </tr>
            ) : (
              filteredCandidates.map((candidate) => {
                const isDuplicate =
                  candidate.email && duplicateEmails[candidate.email] > 1;
                return (
                  <tr
                    key={candidate.user_id}
                    className={`transition-colors ${
                      selectedIds.has(candidate.user_id)
                        ? "bg-blue-50"
                        : isDuplicate
                          ? "bg-amber-50 hover:bg-amber-100"
                          : "hover:bg-slate-50"
                    }`}
                  >
                    <td className={`sticky left-0 z-10 px-4 py-3 ${selectedIds.has(candidate.user_id) ? "bg-blue-50" : isDuplicate ? "bg-amber-50" : "bg-white"}`}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(candidate.user_id)}
                        onChange={() => toggleSelect(candidate.user_id)}
                        className="h-4 w-4 rounded border-slate-300"
                      />
                    </td>
                    <td className={`sticky left-[52px] z-10 whitespace-nowrap border-r border-slate-200 px-4 py-3 font-medium text-slate-900 ${selectedIds.has(candidate.user_id) ? "bg-blue-50" : isDuplicate ? "bg-amber-50" : "bg-white"}`}>
                      <Link
                        href={`/admin/profile/${candidate.user_id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {candidate.full_name || "—"}
                      </Link>
                      {isDuplicate && (
                        <span className="ml-2 text-xs text-amber-600">
                          (duplicate)
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {candidate.title || "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {candidate.city || "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {candidate.state || "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {candidate.work_authorization || "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-slate-600">
                      {candidate.years_experience ?? "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {candidate.email ? (
                        <a
                          href={`mailto:${candidate.email}`}
                          className="text-blue-600 hover:underline"
                        >
                          {candidate.email}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {candidate.phone ? (
                        <a
                          href={`tel:${candidate.phone}`}
                          className="text-blue-600 hover:underline"
                        >
                          {candidate.phone}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <TrustBadge status={candidate.trust_status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center">
                      {candidate.resume_document_id ? (
                        <button
                          type="button"
                          title={candidate.resume_filename || "Preview resume"}
                          onClick={() => {
                            setPreviewResumeId(candidate.resume_document_id);
                            setPreviewFilename(candidate.resume_filename);
                          }}
                          className="inline-flex items-center justify-center rounded-md p-1 text-blue-600 hover:bg-blue-50 hover:text-blue-700 transition-colors"
                        >
                          <svg
                            className="h-5 w-5"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                            />
                          </svg>
                        </button>
                      ) : (
                        <span className="text-slate-300">
                          <svg
                            className="mx-auto h-5 w-5"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                            />
                          </svg>
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {formatDate(candidate.date_added)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {formatDate(candidate.date_modified)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-slate-600">
                      {candidate.match_count}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <Link
                        href={`/admin/candidates/${candidate.user_id}`}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        Matches
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Merge Modal */}
      {showMergeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold">Merge Candidates</h2>
            <p className="mt-2 text-sm text-slate-600">
              Select the primary candidate to keep. All other selected candidates
              will be merged into this one and then deleted.
            </p>

            <div className="mt-4 flex flex-col gap-2">
              {Array.from(selectedIds).map((userId) => {
                const candidate = candidates.find((c) => c.user_id === userId);
                if (!candidate) return null;
                return (
                  <label
                    key={userId}
                    className={`flex items-center gap-3 rounded-xl border p-3 cursor-pointer ${
                      primaryUserId === userId
                        ? "border-blue-500 bg-blue-50"
                        : "border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="primaryUser"
                      checked={primaryUserId === userId}
                      onChange={() => setPrimaryUserId(userId)}
                      className="h-4 w-4"
                    />
                    <div>
                      <div className="font-medium">
                        {candidate.full_name || "Unknown"}
                      </div>
                      <div className="text-xs text-slate-500">
                        {candidate.email}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  setShowMergeModal(false);
                  setPrimaryUserId(null);
                }}
                className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleMerge}
                disabled={!primaryUserId || isMerging}
                className="rounded-full bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {isMerging ? "Merging..." : "Merge Candidates"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resume Preview Modal */}
      {previewResumeId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="flex h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <h2 className="text-lg font-semibold">
                {previewFilename || "Resume Preview"}
              </h2>
              <div className="flex gap-2">
                <a
                  href={`${API_BASE}/api/admin/candidates/resume/${previewResumeId}`}
                  download={previewFilename || "resume"}
                  className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Download
                </a>
                <button
                  type="button"
                  onClick={() => {
                    setPreviewResumeId(null);
                    setPreviewFilename(null);
                    setDocxHtml(null);
                  }}
                  className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden p-4">
              {previewFilename?.toLowerCase().endsWith(".pdf") ? (
                <iframe
                  src={`${API_BASE}/api/admin/candidates/resume/${previewResumeId}`}
                  className="h-full w-full rounded-lg border border-slate-200"
                  title="Resume Preview"
                />
              ) : previewFilename?.toLowerCase().endsWith(".docx") ? (
                docxLoading ? (
                  <div className="flex h-full items-center justify-center text-slate-500">
                    Loading document...
                  </div>
                ) : docxHtml ? (
                  <div
                    className="h-full overflow-auto rounded-lg border border-slate-200 bg-white p-6 prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: docxHtml }}
                  />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-4 text-slate-500">
                    <p>Failed to load document preview.</p>
                    <a
                      href={`${API_BASE}/api/admin/candidates/resume/${previewResumeId}`}
                      download={previewFilename || "resume"}
                      className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                    >
                      Download File
                    </a>
                  </div>
                )
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-slate-500">
                  <p>Preview not available for this file type.</p>
                  <a
                    href={`${API_BASE}/api/admin/candidates/resume/${previewResumeId}`}
                    download={previewFilename || "resume"}
                    className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                  >
                    Download File
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
