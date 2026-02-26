"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Candidate {
  id: number;
  name: string;
  headline: string | null;
  location: string | null;
  skills: string[];
  source: string | null;
  linkedin_url: string | null;
  current_company: string | null;
  about: string | null;
  job_match_count: number;
}

export default function RecruiterCandidates() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/recruiter/candidates`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          const mapped = (data.candidates || []).map((c: Record<string, unknown>) => {
            const pj = (c.profile_json || {}) as Record<string, unknown>;
            const basics = (pj.basics || {}) as Record<string, unknown>;
            const exp = (pj.experience as Record<string, unknown>[] | undefined) || [];
            const firstExp = exp.length > 0 ? exp[0] : null;
            const isPlatform = !pj.source && !pj.sourced_by_user_id;
            return {
              id: c.candidate_profile_id || c.id,
              name: pj.name || basics.name || "Unknown",
              headline: pj.headline || (basics.target_titles as string[] | undefined)?.[0] || (
                firstExp ? [firstExp.title, firstExp.company].filter(Boolean).join(" at ") : null
              ),
              location: pj.location || basics.location || null,
              skills: ((pj.skills as unknown[]) || (basics.top_skills as unknown[]) || []).map(
                (s: unknown) => (typeof s === "string" ? s : (s as Record<string, unknown>)?.name || "")
              ).filter(Boolean) as string[],
              source: isPlatform ? "Winnowcc.ai" : (pj.source as string || null),
              linkedin_url: pj.linkedin_url || null,
              current_company: pj.current_company || (firstExp?.company as string || null),
              about: (pj.about || pj.professional_summary || null) as string | null,
              job_match_count: (c.job_match_count as number) || 0,
            };
          });
          setCandidates(mapped);
        }
      } catch {
        // silently fail
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = candidates.filter((c) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      c.name?.toLowerCase().includes(q) ||
      c.headline?.toLowerCase().includes(q) ||
      c.skills?.some((s) => s.toLowerCase().includes(q))
    );
  });

  const filteredIds = new Set(filtered.map((c) => c.id));
  const allFilteredSelected = filtered.length > 0 && filtered.every((c) => selected.has(c.id));

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allFilteredSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        for (const id of filteredIds) next.delete(id);
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        for (const id of filteredIds) next.add(id);
        return next;
      });
    }
  }

  async function handleDelete() {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} candidate${selected.size !== 1 ? "s" : ""}? This cannot be undone.`)) return;

    setDeleting(true);
    try {
      const params = new URLSearchParams();
      for (const id of selected) params.append("ids", String(id));
      const res = await fetch(`${API_BASE}/api/recruiter/candidates?${params.toString()}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setCandidates((prev) => prev.filter((c) => !selected.has(c.id)));
        setSelected(new Set());
        alert(`${data.deleted} candidate${data.deleted !== 1 ? "s" : ""} deleted.`);
      } else {
        alert("Failed to delete candidates. Please try again.");
      }
    } catch {
      alert("Failed to delete candidates. Please try again.");
    } finally {
      setDeleting(false);
    }
  }

  async function handleExport(format: "csv" | "xlsx") {
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/candidates/export?format=${format}`, {
        credentials: "include",
      });
      if (!res.ok) {
        alert("Export failed. Please try again.");
        return;
      }
      const blob = await res.blob();
      const today = new Date().toISOString().slice(0, 10);
      const ext = format === "xlsx" ? "xlsx" : "csv";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `candidates-${today}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      alert("Export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading candidates...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Candidates</h1>
          <p className="mt-1 text-sm text-slate-500">
            {candidates.length} candidate{candidates.length !== 1 ? "s" : ""} sourced
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/recruiter/candidates/upload"
            className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
          >
            Upload Resumes
          </Link>
          <button
            onClick={() => handleExport("csv")}
            disabled={exporting || candidates.length === 0}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            {exporting ? "Exporting..." : "Export CSV"}
          </button>
          <button
            onClick={() => handleExport("xlsx")}
            disabled={exporting || candidates.length === 0}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            {exporting ? "Exporting..." : "Export Excel"}
          </button>
        </div>
      </div>

      {/* Search */}
      <div>
        <input
          type="text"
          placeholder="Search by name, title, or skill..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        />
      </div>

      {/* Select All + Action Bar */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={allFilteredSelected}
              onChange={toggleSelectAll}
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
            />
            Select all ({filtered.length})
          </label>

          {selected.size > 0 && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
            >
              {deleting ? "Deleting..." : `Delete Selected (${selected.size})`}
            </button>
          )}
        </div>
      )}

      {/* Candidate list */}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <p className="text-slate-500">
            {candidates.length === 0
              ? "No candidates sourced yet. Use the Winnow Chrome extension to source from LinkedIn."
              : "No candidates match your search."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((c) => (
            <div
              key={c.id}
              className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-slate-300"
            >
              {/* Checkbox */}
              <div className="flex items-center pt-1">
                <input
                  type="checkbox"
                  checked={selected.has(c.id)}
                  onChange={() => toggleSelect(c.id)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
              </div>

              {/* Card content (navigable) */}
              <Link
                href={`/recruiter/candidates/${c.id}`}
                className="min-w-0 flex-1"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold text-slate-900 truncate">
                        {c.name}
                      </h3>
                      {c.source === "linkedin_extension" && (
                        <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                          LinkedIn
                        </span>
                      )}
                      {c.source === "Winnowcc.ai" && (
                        <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                          Winnowcc.ai
                        </span>
                      )}
                      {c.job_match_count > 0 && (
                        <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                          {c.job_match_count} job{c.job_match_count !== 1 ? "s" : ""} matched
                        </span>
                      )}
                    </div>
                    {c.headline && (
                      <p className="mt-0.5 text-sm text-slate-600 truncate">{c.headline}</p>
                    )}
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                      {c.location && <span>{c.location}</span>}
                      {c.current_company && <span>{c.current_company}</span>}
                    </div>
                    {c.about && (
                      <p className="mt-1.5 text-xs text-slate-500 line-clamp-2">{c.about}</p>
                    )}
                    {c.skills.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {c.skills.slice(0, 8).map((s) => (
                          <span
                            key={s}
                            className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600"
                          >
                            {s}
                          </span>
                        ))}
                        {c.skills.length > 8 && (
                          <span className="text-xs text-slate-400">
                            +{c.skills.length - 8} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="ml-3 flex shrink-0 items-center gap-2">
                    {c.linkedin_url && (
                      <span
                        onClick={(e) => { e.preventDefault(); window.open(c.linkedin_url!, "_blank"); }}
                        className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
                      >
                        View LinkedIn
                      </span>
                    )}
                    <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
