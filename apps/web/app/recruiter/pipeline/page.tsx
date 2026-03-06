"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import IntroductionRequestModal from "../../components/IntroductionRequestModal";
import { parseApiError } from "../../lib/api-error";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface PipelineCandidate {
  id: number;
  recruiter_job_id: number | null;
  candidate_profile_id: number | null;
  external_name: string | null;
  external_email: string | null;
  external_phone: string | null;
  external_linkedin: string | null;
  source: string | null;
  stage: string;
  rating: number | null;
  tags: string[] | null;
  notes: string | null;
  match_score: number | null;
  outreach_count: number;
  candidate_name: string | null;
  headline: string | null;
  location: string | null;
  current_company: string | null;
  skills: string[] | null;
  linkedin_url: string | null;
  is_platform_candidate: boolean;
  job_match_count: number;
  created_at: string;
}

const STAGES = ["sourced", "contacted", "screening", "interviewing", "offered", "placed", "rejected"];

const STAGE_COLORS: Record<string, string> = {
  sourced: "bg-slate-100 text-slate-700",
  contacted: "bg-blue-100 text-blue-700",
  screening: "bg-amber-100 text-amber-700",
  interviewing: "bg-purple-100 text-purple-700",
  offered: "bg-emerald-100 text-emerald-700",
  placed: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

export default function RecruiterPipeline() {
  const router = useRouter();
  const [entries, setEntries] = useState<PipelineCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [introTarget, setIntroTarget] = useState<{ id: number; name: string } | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Bulk selection
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  // Enroll in Sequence
  const [showEnrollModal, setShowEnrollModal] = useState(false);
  const [availableSequences, setAvailableSequences] = useState<{ id: number; name: string; steps: unknown[] }[]>([]);
  const [enrollSeqId, setEnrollSeqId] = useState<number | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollResult, setEnrollResult] = useState("");

  // Edit modal
  const [editTarget, setEditTarget] = useState<PipelineCandidate | null>(null);
  const [editForm, setEditForm] = useState({ external_name: "", external_email: "", external_phone: "", external_linkedin: "", notes: "", rating: 0 });
  const [editSaving, setEditSaving] = useState(false);

  const [form, setForm] = useState({
    external_name: "",
    external_email: "",
    source: "",
    stage: "sourced",
    notes: "",
  });

  const fetchPipeline = useCallback(async () => {
    try {
      setFetchError("");
      const url = new URL(`${API_BASE}/api/recruiter/pipeline`);
      if (stageFilter) url.searchParams.set("stage", stageFilter);
      if (searchQuery.trim()) url.searchParams.set("search", searchQuery.trim());
      url.searchParams.set("limit", "100");
      const res = await fetch(url.toString(), { credentials: "include" });
      if (res.ok) {
        setEntries(await res.json());
      } else {
        const body = await res.json().catch(() => null);
        setFetchError(body?.detail || `Failed to load pipeline (${res.status})`);
      }
    } catch {
      setFetchError("Network error loading pipeline");
    }
  }, [stageFilter, searchQuery]);

  useEffect(() => {
    setLoading(true);
    fetchPipeline().finally(() => setLoading(false));
  }, [stageFilter, fetchPipeline]);

  // Debounced search
  function handleSearchChange(value: string) {
    setSearchQuery(value);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setSelected(new Set());
    }, 300);
  }

  // Selection helpers
  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === entries.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(entries.map((e) => e.id)));
    }
  }

  // Bulk actions
  async function handleBulkDelete() {
    if (!confirm(`Delete ${selected.size} selected candidate(s) from the pipeline?`)) return;
    setBulkLoading(true);
    try {
      const url = new URL(`${API_BASE}/api/recruiter/pipeline/bulk-delete`);
      selected.forEach((id) => url.searchParams.append("ids", String(id)));
      const res = await fetch(url.toString(), { method: "POST", credentials: "include" });
      if (res.ok) {
        setSelected(new Set());
        fetchPipeline();
      }
    } catch {
      /* ignore */
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleBulkStageChange(newStage: string) {
    setBulkLoading(true);
    try {
      const url = new URL(`${API_BASE}/api/recruiter/pipeline/bulk-stage`);
      selected.forEach((id) => url.searchParams.append("ids", String(id)));
      url.searchParams.set("new_stage", newStage);
      const res = await fetch(url.toString(), { method: "PATCH", credentials: "include" });
      if (res.ok) {
        setSelected(new Set());
        fetchPipeline();
      }
    } catch {
      /* ignore */
    } finally {
      setBulkLoading(false);
    }
  }

  // Edit modal
  function openEditModal(entry: PipelineCandidate) {
    setEditTarget(entry);
    setEditForm({
      external_name: entry.external_name || "",
      external_email: entry.external_email || "",
      external_phone: entry.external_phone || "",
      external_linkedin: entry.external_linkedin || entry.linkedin_url || "",
      notes: entry.notes || "",
      rating: entry.rating || 0,
    });
  }

  async function handleEditSave() {
    if (!editTarget) return;
    setEditSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (editForm.external_name) body.external_name = editForm.external_name;
      if (editForm.external_email) body.external_email = editForm.external_email;
      if (editForm.external_phone) body.external_phone = editForm.external_phone;
      if (editForm.external_linkedin) body.external_linkedin = editForm.external_linkedin;
      body.notes = editForm.notes || null;
      body.rating = editForm.rating || null;

      const res = await fetch(`${API_BASE}/api/recruiter/pipeline/${editTarget.id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setEditTarget(null);
        fetchPipeline();
      }
    } catch {
      /* ignore */
    } finally {
      setEditSaving(false);
    }
  }

  async function openEnrollModal() {
    setEnrollResult("");
    setEnrollSeqId(null);
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/sequences`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setAvailableSequences(data.filter((s: { is_active: boolean }) => s.is_active));
      }
    } catch {
      /* ignore */
    }
    setShowEnrollModal(true);
  }

  async function handleEnroll() {
    if (!enrollSeqId) return;
    setEnrolling(true);
    setEnrollResult("");
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/sequences/${enrollSeqId}/enroll`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline_candidate_ids: Array.from(selected) }),
      });
      const data = await res.json();
      if (res.ok) {
        setEnrollResult(`Enrolled ${data.enrolled}, skipped ${data.skipped}${data.no_email ? `, ${data.no_email} missing email` : ""}`);
        setSelected(new Set());
        setTimeout(() => setShowEnrollModal(false), 2000);
      } else {
        setEnrollResult(parseApiError(data, "Failed to enroll"));
      }
    } catch {
      setEnrollResult("Network error");
    } finally {
      setEnrolling(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError("");
    const body: Record<string, unknown> = { stage: form.stage, source: form.source || "manual" };
    if (form.external_name) body.external_name = form.external_name;
    if (form.external_email) body.external_email = form.external_email;
    if (form.notes) body.notes = form.notes;

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/pipeline`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowForm(false);
        setForm({ external_name: "", external_email: "", source: "", stage: "sourced", notes: "" });
        fetchPipeline();
      } else {
        const data = await res.json();
        setError(parseApiError(data, "Failed to add candidate"));
      }
    } catch {
      setError("Network error");
    } finally {
      setCreating(false);
    }
  }

  async function handleStageChange(id: number, newStage: string) {
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/pipeline/${id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: newStage }),
      });
      if (res.ok) fetchPipeline();
    } catch {
      /* ignore */
    }
  }

  async function handleRemove(id: number) {
    if (!confirm("Remove this candidate from the pipeline?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/pipeline/${id}`, { method: "DELETE", credentials: "include" });
      if (res.ok) fetchPipeline();
    } catch {
      /* ignore */
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center py-20"><div className="text-sm text-slate-500">Loading pipeline...</div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Pipeline</h1>
          <p className="mt-1 text-sm text-slate-500">Track candidates through your hiring process</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
          {showForm ? "Cancel" : "+ Add to Pipeline"}
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Add Candidate</h2>
          {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Name *</label>
                <input type="text" required value={form.external_name} onChange={(e) => setForm({ ...form, external_name: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" placeholder="Candidate name" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input type="email" value={form.external_email} onChange={(e) => setForm({ ...form, external_email: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Source</label>
                <input type="text" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" placeholder="e.g. LinkedIn" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Notes</label>
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
            </div>
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setShowForm(false)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="submit" disabled={creating} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{creating ? "Adding..." : "Add to Pipeline"}</button>
            </div>
          </form>
        </div>
      )}

      {/* Search bar */}
      <input
        type="text"
        placeholder="Search by name or email..."
        value={searchQuery}
        onChange={(e) => handleSearchChange(e.target.value)}
        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
      />

      {/* Stage filter pills */}
      <div className="flex flex-wrap gap-2">
        {["", ...STAGES].map((s) => (
          <button key={s} onClick={() => setStageFilter(s)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${stageFilter === s ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {s || "All"}
          </button>
        ))}
      </div>

      {/* Bulk action toolbar */}
      {selected.size > 0 && (
        <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-3 shadow-md sm:gap-4">
          <span className="text-sm font-medium text-slate-700">{selected.size} selected</span>
          <select
            defaultValue=""
            onChange={(ev) => {
              if (ev.target.value) handleBulkStageChange(ev.target.value);
              ev.target.value = "";
            }}
            disabled={bulkLoading}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            <option value="" disabled>Change Stage...</option>
            {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={openEnrollModal} disabled={bulkLoading} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            Enroll in Sequence
          </button>
          <button onClick={handleBulkDelete} disabled={bulkLoading} className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
            Delete Selected
          </button>
          <button onClick={() => setSelected(new Set())} className="text-sm text-slate-500 hover:text-slate-700">
            Deselect All
          </button>
        </div>
      )}

      {/* Fetch error */}
      {fetchError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {fetchError}
          <button onClick={() => fetchPipeline()} className="ml-3 font-medium underline hover:text-red-900">Retry</button>
        </div>
      )}

      {/* Pipeline entries */}
      {!fetchError && entries.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <p className="text-slate-500">No candidates in pipeline yet. Source candidates and add them to your pipeline.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Select All */}
          <label className="flex items-center gap-2 px-1 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={entries.length > 0 && selected.size === entries.length}
              onChange={toggleSelectAll}
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
            />
            Select All ({entries.length})
          </label>

          {entries.map((entry) => (
            <div
              key={entry.id}
              className={`flex flex-col gap-3 rounded-xl border bg-white p-4 shadow-sm transition-colors sm:flex-row sm:items-start sm:gap-4 sm:p-5 ${selected.has(entry.id) ? "border-slate-400 bg-slate-50" : "border-slate-200"} ${entry.candidate_profile_id ? "cursor-pointer hover:border-slate-300 hover:bg-slate-50/50" : ""}`}
              onClick={() => {
                if (entry.candidate_profile_id) router.push(`/recruiter/candidates/${entry.candidate_profile_id}`);
              }}
            >
              {/* Checkbox */}
              <div className="flex pt-0.5" onClick={(ev) => ev.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={selected.has(entry.id)}
                  onChange={() => toggleSelect(entry.id)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                  <h3 className="text-base font-semibold text-slate-900">{entry.candidate_name || entry.external_name || `Candidate #${entry.id}`}</h3>
                  {entry.match_score != null && (
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">{Math.round(entry.match_score)}% match</span>
                  )}
                  {entry.job_match_count > 0 && (
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                      {entry.job_match_count} job{entry.job_match_count !== 1 ? "s" : ""} matched
                    </span>
                  )}
                  {entry.rating != null && (
                    <span className="text-xs text-amber-500">{"★".repeat(entry.rating)}{"☆".repeat(5 - entry.rating)}</span>
                  )}
                  {entry.linkedin_url && (
                    <span
                      onClick={(ev) => { ev.stopPropagation(); window.open(entry.linkedin_url!, "_blank"); }}
                      className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                    >
                      LinkedIn
                    </span>
                  )}
                </div>
                {entry.headline && <p className="mt-0.5 text-sm text-slate-600 truncate">{entry.headline}</p>}
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
                  {entry.location && <span>{entry.location}</span>}
                  {entry.current_company && <span>{entry.current_company}</span>}
                  {entry.external_email && <span>{entry.external_email}</span>}
                  {entry.source && <span>via {entry.source}</span>}
                </div>
                {entry.skills && entry.skills.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {entry.skills.slice(0, 6).map((s) => (
                      <span key={s} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">{s}</span>
                    ))}
                    {entry.skills.length > 6 && (
                      <span className="text-xs text-slate-400">+{entry.skills.length - 6} more</span>
                    )}
                  </div>
                )}
                {entry.notes && <p className="mt-1.5 max-w-lg truncate text-xs text-slate-400 italic">{entry.notes}</p>}
                {entry.tags && entry.tags.length > 0 && (
                  <div className="mt-1.5 flex items-center gap-1.5">
                    {entry.tags.map((t) => (
                      <span key={t} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-700">{t}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2 sm:ml-2 sm:gap-3" onClick={(ev) => ev.stopPropagation()}>
                {entry.candidate_profile_id && entry.is_platform_candidate && (
                  <button
                    onClick={() => setIntroTarget({ id: entry.candidate_profile_id!, name: entry.candidate_name || entry.external_name || `Candidate #${entry.id}` })}
                    className="rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-800"
                    title="Request Introduction"
                  >
                    Intro
                  </button>
                )}
                <select
                  value={entry.stage}
                  onChange={(ev) => handleStageChange(entry.id, ev.target.value)}
                  className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${STAGE_COLORS[entry.stage] || "bg-slate-100 text-slate-600"} border-0 focus:ring-1 focus:ring-slate-400`}
                >
                  {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                {/* Edit button */}
                <button onClick={() => openEditModal(entry)} className="text-xs text-slate-400 hover:text-slate-600" title="Edit contact">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                </button>
                <button onClick={() => handleRemove(entry.id)} className="text-xs text-slate-400 hover:text-red-500" title="Remove">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
                {entry.candidate_profile_id && (
                  <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Contact Modal */}
      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditTarget(null)}>
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(ev) => ev.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">Edit Contact</h2>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
                <input type="text" value={editForm.external_name} onChange={(e) => setEditForm({ ...editForm, external_name: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input type="email" value={editForm.external_email} onChange={(e) => setEditForm({ ...editForm, external_email: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Phone</label>
                <input type="text" value={editForm.external_phone} onChange={(e) => setEditForm({ ...editForm, external_phone: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">LinkedIn URL</label>
                <input type="text" value={editForm.external_linkedin} onChange={(e) => setEditForm({ ...editForm, external_linkedin: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Notes</label>
                <textarea value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} rows={3} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Rating</label>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setEditForm({ ...editForm, rating: editForm.rating === star ? 0 : star })}
                      className={`text-xl ${star <= editForm.rating ? "text-amber-500" : "text-slate-300"} hover:text-amber-400`}
                    >
                      ★
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button onClick={() => setEditTarget(null)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button onClick={handleEditSave} disabled={editSaving} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{editSaving ? "Saving..." : "Save"}</button>
            </div>
          </div>
        </div>
      )}

      {introTarget && (
        <IntroductionRequestModal
          candidateProfileId={introTarget.id}
          candidateName={introTarget.name}
          onClose={() => setIntroTarget(null)}
          onSuccess={() => {
            setIntroTarget(null);
            fetchPipeline();
          }}
        />
      )}

      {/* Enroll in Sequence Modal */}
      {showEnrollModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowEnrollModal(false)}>
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(ev) => ev.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">Enroll in Outreach Sequence</h2>
            <p className="mb-4 text-sm text-slate-500">{selected.size} candidate(s) selected</p>
            {availableSequences.length === 0 ? (
              <p className="text-sm text-slate-500">No active sequences available. <a href="/recruiter/sequences" className="text-blue-600 hover:underline">Create one first</a>.</p>
            ) : (
              <div className="space-y-3">
                <select
                  value={enrollSeqId ?? ""}
                  onChange={(e) => setEnrollSeqId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="">Select a sequence...</option>
                  {availableSequences.map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.steps.length} steps)</option>
                  ))}
                </select>
                {enrollResult && (
                  <div className={`rounded-md p-3 text-sm ${enrollResult.startsWith("Enrolled") ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                    {enrollResult}
                  </div>
                )}
              </div>
            )}
            <div className="mt-5 flex justify-end gap-3">
              <button onClick={() => setShowEnrollModal(false)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              {availableSequences.length > 0 && (
                <button onClick={handleEnroll} disabled={enrolling || !enrollSeqId} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                  {enrolling ? "Enrolling..." : "Enroll"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
