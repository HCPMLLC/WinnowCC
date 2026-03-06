"use client";

import { useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface CandidateResult {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  years_experience: number | null;
  top_skills: string[];
  match_score: number | null;
  profile_visibility: string;
  preferred_locations: string[];
  remote_ok: boolean | null;
  willing_to_relocate: boolean | null;
}

interface SearchResponse {
  results: CandidateResult[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export default function CandidateSearchPage() {
  const [skillsInput, setSkillsInput] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [titleInput, setTitleInput] = useState("");
  const [results, setResults] = useState<CandidateResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());

  async function handleSearch(searchPage = 1) {
    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    const filters: Record<string, string[] | number[]> = {};
    if (skillsInput.trim()) {
      filters.skills = skillsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    if (locationInput.trim()) {
      filters.locations = locationInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    if (titleInput.trim()) {
      filters.job_titles = titleInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }

    try {
      const url = new URL(`${API_BASE}/api/employer/candidates/search`);
      url.searchParams.set("page", String(searchPage));

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(filters),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Search failed");
      }

      const data: SearchResponse = await res.json();
      setResults(data.results);
      setTotal(data.total);
      setPage(data.page);
      setHasMore(data.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function saveCandidate(candidateId: number) {
    setSavingId(candidateId);
    try {
      const res = await fetch(`${API_BASE}/api/employer/candidates/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ candidate_id: candidateId }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to save candidate");
      }
      setSavedIds((prev) => new Set([...prev, candidateId]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">
          Candidate Search
        </h1>
        <p className="mt-1 text-slate-600">
          Find talent that matches your requirements
        </p>
      </div>

      {/* Search Filters */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Skills
            </label>
            <input
              type="text"
              value={skillsInput}
              onChange={(e) => setSkillsInput(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="React, Python, SQL..."
            />
            <p className="mt-1 text-xs text-slate-400">
              Comma-separated skills
            </p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Location
            </label>
            <input
              type="text"
              value={locationInput}
              onChange={(e) => setLocationInput(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="San Francisco, Remote..."
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Job Titles
            </label>
            <input
              type="text"
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="Engineer, Designer..."
            />
          </div>
        </div>
        <button
          onClick={() => handleSearch(1)}
          disabled={isLoading}
          className="mt-4 rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isLoading ? "Searching..." : "Search Candidates"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {hasSearched && !isLoading && (
        <div className="mb-4 text-sm text-slate-600">
          Found {total} candidate{total !== 1 ? "s" : ""}
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      )}

      {!isLoading && results.length > 0 && (
        <div className="space-y-4">
          {results.map((candidate) => (
            <div
              key={candidate.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                    <Link
                      href={`/employer/candidates/${candidate.id}`}
                      className="text-lg font-semibold text-slate-900 hover:text-blue-600"
                    >
                      {candidate.name}
                    </Link>
                    {candidate.profile_visibility === "anonymous" && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                        Anonymous
                      </span>
                    )}
                  </div>
                  {candidate.headline && (
                    <p className="mt-1 text-sm text-slate-600">
                      {candidate.headline}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
                    {candidate.location && <span>{candidate.location}</span>}
                    {candidate.years_experience != null && (
                      <span>{candidate.years_experience} years exp.</span>
                    )}
                    {candidate.remote_ok === true && (
                      <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                        Remote OK
                      </span>
                    )}
                    {candidate.remote_ok === false && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        On-site
                      </span>
                    )}
                    {candidate.willing_to_relocate === true && (
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                        Will relocate
                      </span>
                    )}
                  </div>
                  {(candidate.preferred_locations ?? []).length > 0 && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                      <span className="font-medium">Preferred:</span>
                      {(candidate.preferred_locations ?? []).map((loc, i) => (
                        <span
                          key={i}
                          className="rounded-full bg-blue-50 px-2 py-0.5 font-medium text-blue-700"
                        >
                          {loc}
                        </span>
                      ))}
                    </div>
                  )}
                  {(candidate.top_skills ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(candidate.top_skills ?? []).map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                        >
                          {typeof skill === "string" ? skill : String(skill)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 sm:ml-4">
                  <Link
                    href={`/employer/candidates/${candidate.id}`}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    View
                  </Link>
                  <button
                    onClick={() => saveCandidate(candidate.id)}
                    disabled={
                      savingId === candidate.id || savedIds.has(candidate.id)
                    }
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {savedIds.has(candidate.id) ? "Saved" : "Save"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLoading && hasSearched && results.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-lg font-semibold text-slate-900">
            No candidates found
          </h3>
          <p className="mt-2 text-slate-600">
            Try adjusting your search filters for broader results.
          </p>
        </div>
      )}

      {/* Pagination */}
      {!isLoading && results.length > 0 && (
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => handleSearch(page - 1)}
            disabled={page <= 1}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-slate-500">Page {page}</span>
          <button
            onClick={() => handleSearch(page + 1)}
            disabled={!hasMore}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
