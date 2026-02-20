"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface OutreachStep {
  step_number: number;
  delay_days: number;
  subject: string;
  body: string;
}

interface OutreachSequence {
  id: number;
  name: string;
  description: string | null;
  recruiter_job_id: number | null;
  is_active: boolean;
  steps: OutreachStep[];
  enrolled_count: number;
  sent_count: number;
  created_at: string;
  updated_at: string | null;
}

interface Enrollment {
  id: number;
  sequence_id: number;
  pipeline_candidate_id: number;
  current_step: number;
  status: string;
  next_send_at: string | null;
  last_sent_at: string | null;
  enrolled_at: string | null;
  completed_at: string | null;
  candidate_name: string | null;
  candidate_email: string | null;
}

interface RecruiterJob {
  id: number;
  title: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  completed: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-700",
  unenrolled: "bg-slate-100 text-slate-600",
  bounced: "bg-red-100 text-red-700",
};

const TEMPLATE_VARS = [
  { var: "{candidate_name}", desc: "Candidate's name" },
  { var: "{job_title}", desc: "Linked job title" },
  { var: "{job_location}", desc: "Job location" },
  { var: "{recruiter_name}", desc: "Your company name" },
  { var: "{recruiter_company}", desc: "Your company name" },
];

export default function RecruiterSequences() {
  const [sequences, setSequences] = useState<OutreachSequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [tierBlocked, setTierBlocked] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingSeq, setEditingSeq] = useState<OutreachSequence | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Form state
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formJobId, setFormJobId] = useState<number | null>(null);
  const [formSteps, setFormSteps] = useState<OutreachStep[]>([
    { step_number: 1, delay_days: 0, subject: "", body: "" },
  ]);

  // Enrollment view
  const [viewingSeqId, setViewingSeqId] = useState<number | null>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [enrollLoading, setEnrollLoading] = useState(false);

  // Jobs for dropdown
  const [jobs, setJobs] = useState<RecruiterJob[]>([]);

  const fetchSequences = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/sequences`, {
        credentials: "include",
      });
      if (res.status === 403) {
        setTierBlocked(true);
        return;
      }
      if (res.ok) {
        setSequences(await res.json());
        setTierBlocked(false);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/jobs`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(Array.isArray(data) ? data : data.jobs || []);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    Promise.all([fetchSequences(), fetchJobs()]).finally(() =>
      setLoading(false)
    );
  }, [fetchSequences, fetchJobs]);

  function openCreate() {
    setEditingSeq(null);
    setFormName("");
    setFormDesc("");
    setFormJobId(null);
    setFormSteps([{ step_number: 1, delay_days: 0, subject: "", body: "" }]);
    setError("");
    setShowModal(true);
  }

  function openEdit(seq: OutreachSequence) {
    setEditingSeq(seq);
    setFormName(seq.name);
    setFormDesc(seq.description || "");
    setFormJobId(seq.recruiter_job_id);
    setFormSteps(
      seq.steps.length > 0
        ? seq.steps
        : [{ step_number: 1, delay_days: 0, subject: "", body: "" }]
    );
    setError("");
    setShowModal(true);
  }

  function addStep() {
    if (formSteps.length >= 10) return;
    setFormSteps([
      ...formSteps,
      {
        step_number: formSteps.length + 1,
        delay_days: 3,
        subject: "",
        body: "",
      },
    ]);
  }

  function removeStep(index: number) {
    if (formSteps.length <= 1) return;
    const updated = formSteps
      .filter((_, i) => i !== index)
      .map((s, i) => ({ ...s, step_number: i + 1 }));
    setFormSteps(updated);
  }

  function updateStep(index: number, field: keyof OutreachStep, value: string | number) {
    const updated = [...formSteps];
    updated[index] = { ...updated[index], [field]: value };
    setFormSteps(updated);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    const body: Record<string, unknown> = {
      name: formName,
      description: formDesc || null,
      recruiter_job_id: formJobId,
      steps: formSteps,
    };

    try {
      const url = editingSeq
        ? `${API_BASE}/api/recruiter/sequences/${editingSeq.id}`
        : `${API_BASE}/api/recruiter/sequences`;
      const method = editingSeq ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowModal(false);
        fetchSequences();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to save sequence");
      }
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this sequence and all its enrollments?")) return;
    try {
      await fetch(`${API_BASE}/api/recruiter/sequences/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      fetchSequences();
      if (viewingSeqId === id) setViewingSeqId(null);
    } catch {
      /* ignore */
    }
  }

  async function handleToggleActive(seq: OutreachSequence) {
    try {
      await fetch(`${API_BASE}/api/recruiter/sequences/${seq.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !seq.is_active }),
      });
      fetchSequences();
    } catch {
      /* ignore */
    }
  }

  async function viewEnrollments(seqId: number) {
    setViewingSeqId(seqId);
    setEnrollLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/sequences/${seqId}/enrollments`,
        { credentials: "include" }
      );
      if (res.ok) setEnrollments(await res.json());
    } catch {
      /* ignore */
    } finally {
      setEnrollLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading sequences...</div>
      </div>
    );
  }

  if (tierBlocked) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">Outreach Sequences</h1>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
            <svg className="h-6 w-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-amber-900">Upgrade to Unlock Outreach Sequences</h2>
          <p className="mt-2 text-sm text-amber-700">
            Automated multi-step email outreach is available on Team and Agency plans.
            Create sequences, enroll candidates, and let Winnow handle follow-ups automatically.
          </p>
          <a href="/recruiter/settings" className="mt-4 inline-block rounded-md bg-amber-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-amber-700">
            View Plans
          </a>
        </div>
      </div>
    );
  }

  const viewingSeq = sequences.find((s) => s.id === viewingSeqId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Outreach Sequences</h1>
          <p className="mt-1 text-sm text-slate-500">
            Automate multi-step email campaigns for pipeline candidates
          </p>
        </div>
        <button
          onClick={openCreate}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          + New Sequence
        </button>
      </div>

      {/* Sequence list */}
      {sequences.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <p className="text-slate-500">
            No sequences yet. Create one to start automating your outreach.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="px-4 py-3 font-medium text-slate-600">Name</th>
                <th className="px-4 py-3 font-medium text-slate-600">Status</th>
                <th className="px-4 py-3 font-medium text-slate-600">Steps</th>
                <th className="px-4 py-3 font-medium text-slate-600">Enrolled</th>
                <th className="px-4 py-3 font-medium text-slate-600">Sent</th>
                <th className="px-4 py-3 font-medium text-slate-600">Created</th>
                <th className="px-4 py-3 font-medium text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sequences.map((seq) => (
                <tr key={seq.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <button
                      onClick={() => viewEnrollments(seq.id)}
                      className="font-medium text-slate-900 hover:text-blue-600"
                    >
                      {seq.name}
                    </button>
                    {seq.description && (
                      <p className="mt-0.5 text-xs text-slate-400 truncate max-w-xs">
                        {seq.description}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        seq.is_active
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {seq.is_active ? "Active" : "Paused"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{seq.steps.length}</td>
                  <td className="px-4 py-3 text-slate-600">{seq.enrolled_count}</td>
                  <td className="px-4 py-3 text-slate-600">{seq.sent_count}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {seq.created_at
                      ? new Date(seq.created_at).toLocaleDateString()
                      : "-"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleActive(seq)}
                        className="text-xs text-slate-500 hover:text-slate-700"
                      >
                        {seq.is_active ? "Pause" : "Resume"}
                      </button>
                      <button
                        onClick={() => openEdit(seq)}
                        className="text-xs text-slate-500 hover:text-slate-700"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(seq.id)}
                        className="text-xs text-red-400 hover:text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Enrollment view */}
      {viewingSeq && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              Enrollments: {viewingSeq.name}
            </h2>
            <button
              onClick={() => setViewingSeqId(null)}
              className="text-sm text-slate-400 hover:text-slate-600"
            >
              Close
            </button>
          </div>
          {enrollLoading ? (
            <p className="text-sm text-slate-500">Loading enrollments...</p>
          ) : enrollments.length === 0 ? (
            <p className="text-sm text-slate-500">
              No candidates enrolled yet. Use the Pipeline page to enroll candidates.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 font-medium text-slate-600">
                      Candidate
                    </th>
                    <th className="px-3 py-2 font-medium text-slate-600">Email</th>
                    <th className="px-3 py-2 font-medium text-slate-600">
                      Progress
                    </th>
                    <th className="px-3 py-2 font-medium text-slate-600">Status</th>
                    <th className="px-3 py-2 font-medium text-slate-600">
                      Next Send
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {enrollments.map((e) => (
                    <tr key={e.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 text-slate-900">
                        {e.candidate_name || `Candidate #${e.pipeline_candidate_id}`}
                      </td>
                      <td className="px-3 py-2 text-slate-500">
                        {e.candidate_email || "-"}
                      </td>
                      <td className="px-3 py-2 text-slate-600">
                        {e.current_step} / {viewingSeq.steps.length}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                            STATUS_COLORS[e.status] || "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {e.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {e.next_send_at
                          ? new Date(e.next_send_at).toLocaleString()
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4"
          onClick={() => setShowModal(false)}
        >
          <div
            className="my-8 w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-4 text-lg font-semibold text-slate-900">
              {editingSeq ? "Edit Sequence" : "New Outreach Sequence"}
            </h2>

            {error && (
              <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Sequence Name *
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="e.g., Senior Engineer Outreach"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Description
                </label>
                <input
                  type="text"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="Optional description"
                />
              </div>

              {jobs.length > 0 && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    Linked Job (optional)
                  </label>
                  <select
                    value={formJobId ?? ""}
                    onChange={(e) =>
                      setFormJobId(e.target.value ? Number(e.target.value) : null)
                    }
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  >
                    <option value="">No linked job</option>
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Template variables helper */}
              <div className="rounded-md bg-slate-50 p-3">
                <p className="mb-1 text-xs font-medium text-slate-600">
                  Template Variables
                </p>
                <div className="flex flex-wrap gap-2">
                  {TEMPLATE_VARS.map((tv) => (
                    <span
                      key={tv.var}
                      className="rounded bg-white px-2 py-0.5 text-xs text-slate-500 border border-slate-200"
                      title={tv.desc}
                    >
                      {tv.var}
                    </span>
                  ))}
                </div>
              </div>

              {/* Steps */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-sm font-medium text-slate-700">
                    Steps ({formSteps.length}/10)
                  </label>
                  <button
                    type="button"
                    onClick={addStep}
                    disabled={formSteps.length >= 10}
                    className="text-xs text-blue-600 hover:text-blue-700 disabled:text-slate-400"
                  >
                    + Add Step
                  </button>
                </div>
                <div className="space-y-4">
                  {formSteps.map((step, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-slate-200 p-4"
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-700">
                          Step {i + 1}
                        </span>
                        {formSteps.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeStep(i)}
                            className="text-xs text-red-400 hover:text-red-600"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                      <div className="mb-2">
                        <label className="mb-1 block text-xs text-slate-500">
                          Delay (days after {i === 0 ? "enrollment" : "previous step"})
                        </label>
                        <input
                          type="number"
                          min={0}
                          value={step.delay_days}
                          onChange={(e) =>
                            updateStep(i, "delay_days", parseInt(e.target.value) || 0)
                          }
                          className="w-24 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                        />
                      </div>
                      <div className="mb-2">
                        <label className="mb-1 block text-xs text-slate-500">
                          Subject
                        </label>
                        <input
                          type="text"
                          value={step.subject}
                          onChange={(e) =>
                            updateStep(i, "subject", e.target.value)
                          }
                          className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                          placeholder="Email subject line"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-500">
                          Body
                        </label>
                        <textarea
                          value={step.body}
                          onChange={(e) =>
                            updateStep(i, "body", e.target.value)
                          }
                          rows={3}
                          className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                          placeholder="Email body (HTML supported, use template variables)"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !formName.trim() || formSteps.some((s) => !s.subject.trim() || !s.body.trim())}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {saving ? "Saving..." : editingSeq ? "Update Sequence" : "Create Sequence"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
