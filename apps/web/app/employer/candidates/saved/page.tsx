"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface CandidateSearchResult {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  profile_visibility: string;
}

interface SavedCandidate {
  id: number;
  candidate_id: number;
  notes: string | null;
  saved_at: string;
  candidate: CandidateSearchResult | null;
}

export default function SavedCandidatesPage() {
  const [savedList, setSavedList] = useState<SavedCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingNotes, setEditingNotes] = useState<number | null>(null);
  const [notesText, setNotesText] = useState("");

  useEffect(() => {
    fetchSaved();
  }, []);

  async function fetchSaved() {
    try {
      const res = await fetch(`${API_BASE}/api/employer/candidates/saved`, {
        credentials: "include",
      });
      if (!res.ok) {
        throw new Error("Failed to load saved candidates");
      }
      setSavedList(await res.json());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load saved candidates",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function updateNotes(savedId: number) {
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/candidates/saved/${savedId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ notes: notesText }),
        },
      );
      if (!res.ok) {
        throw new Error("Failed to update notes");
      }
      const updated = await res.json();
      setSavedList((prev) =>
        prev.map((s) =>
          s.id === savedId ? { ...s, notes: updated.notes } : s,
        ),
      );
      setEditingNotes(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update notes");
    }
  }

  async function unsaveCandidate(savedId: number) {
    if (!confirm("Remove this candidate from your saved list?")) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/candidates/saved/${savedId}`,
        {
          method: "DELETE",
          credentials: "include",
        },
      );
      if (!res.ok && res.status !== 204) {
        throw new Error("Failed to remove candidate");
      }
      setSavedList((prev) => prev.filter((s) => s.id !== savedId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove");
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="h-28 animate-pulse rounded-xl border border-slate-200 bg-white"
          />
        ))}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">
          Saved Candidates
        </h1>
        <p className="mt-1 text-slate-600">
          Your shortlisted talent ({savedList.length} saved)
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {savedList.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-lg font-semibold text-slate-900">
            No saved candidates yet
          </h3>
          <p className="mt-2 text-slate-600">
            Search for candidates and save your favorites here.
          </p>
          <Link
            href="/employer/candidates"
            className="mt-4 inline-block rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Search Candidates
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {savedList.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <Link
                      href={`/employer/candidates/${item.candidate_id}`}
                      className="text-lg font-semibold text-slate-900 hover:text-blue-600"
                    >
                      {item.candidate?.name ?? `Candidate ${item.candidate_id}`}
                    </Link>
                    <span className="text-xs text-slate-400">
                      Saved{" "}
                      {new Date(item.saved_at).toLocaleDateString()}
                    </span>
                  </div>

                  {item.candidate?.headline && (
                    <p className="mt-1 text-sm text-slate-600">
                      {item.candidate.headline}
                    </p>
                  )}

                  <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-500">
                    {item.candidate?.location && (
                      <span>{item.candidate.location}</span>
                    )}
                    {item.candidate?.years_experience != null && (
                      <span>
                        {item.candidate.years_experience} years exp.
                      </span>
                    )}
                  </div>

                  {item.candidate?.top_skills &&
                    item.candidate.top_skills.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {item.candidate.top_skills.map((skill) => (
                          <span
                            key={skill}
                            className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                          >
                            {typeof skill === "string"
                              ? skill
                              : String(skill)}
                          </span>
                        ))}
                      </div>
                    )}

                  {/* Notes */}
                  <div className="mt-3">
                    {editingNotes === item.id ? (
                      <div className="flex items-end gap-2">
                        <textarea
                          value={notesText}
                          onChange={(e) => setNotesText(e.target.value)}
                          rows={2}
                          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                        />
                        <button
                          onClick={() => updateNotes(item.id)}
                          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingNotes(null)}
                          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-start gap-2">
                        <p className="text-sm text-slate-500">
                          {item.notes ? (
                            <>
                              <span className="font-medium text-slate-700">
                                Notes:
                              </span>{" "}
                              {item.notes}
                            </>
                          ) : (
                            <span className="italic text-slate-400">
                              No notes
                            </span>
                          )}
                        </p>
                        <button
                          onClick={() => {
                            setEditingNotes(item.id);
                            setNotesText(item.notes || "");
                          }}
                          className="text-xs font-medium text-blue-600 hover:text-blue-700"
                        >
                          Edit
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="ml-4 flex flex-col gap-2">
                  <Link
                    href={`/employer/candidates/${item.candidate_id}`}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-center text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    View
                  </Link>
                  <button
                    onClick={() => unsaveCandidate(item.id)}
                    className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
