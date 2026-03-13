"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Step {
  delay_days: number;
  subject: string;
  body: string;
  action: string;
}

const TEMPLATE_VARS = [
  "{candidate_name}",
  "{company_name}",
  "{job_title}",
  "{job_location}",
  "{career_page_url}",
];

export default function NewSequencePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [employerJobId, setEmployerJobId] = useState("");
  const [steps, setSteps] = useState<Step[]>([
    {
      delay_days: 0,
      subject: "Exciting opportunity at {company_name}",
      body: "Hi {candidate_name},\n\nWe have a {job_title} position that matches your experience.",
      action: "invite_to_apply",
    },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addStep() {
    setSteps([
      ...steps,
      { delay_days: 3, subject: "", body: "", action: "followup" },
    ]);
  }

  function updateStep(index: number, field: keyof Step, value: string | number) {
    const updated = [...steps];
    (updated[index] as Record<string, unknown>)[field] = value;
    setSteps(updated);
  }

  function removeStep(index: number) {
    if (steps.length <= 1) return;
    setSteps(steps.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/employer/outreach/sequences`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            description: description || null,
            employer_job_id: employerJobId ? parseInt(employerJobId) : null,
            steps,
          }),
        },
      );
      if (res.ok) {
        const data = await res.json();
        router.push(`/employer/outreach/${data.id}`);
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Failed to create sequence");
      }
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl py-8">
      <h1 className="mb-6 text-2xl font-bold text-slate-900">
        New Outreach Sequence
      </h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Sequence Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                placeholder="e.g., Senior Engineer Outreach"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Description (optional)
              </label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Linked Job ID (optional)
              </label>
              <input
                value={employerJobId}
                onChange={(e) => setEmployerJobId(e.target.value)}
                type="number"
                className="mt-1 w-48 rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Steps</h2>
            <div className="flex flex-wrap gap-1 text-[10px] text-slate-400">
              {TEMPLATE_VARS.map((v) => (
                <code key={v} className="rounded bg-slate-100 px-1">
                  {v}
                </code>
              ))}
            </div>
          </div>

          {steps.map((step, i) => (
            <div
              key={i}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">
                  Step {i + 1}
                </span>
                {steps.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeStep(i)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-500">
                    Delay (days)
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={step.delay_days}
                    onChange={(e) =>
                      updateStep(i, "delay_days", parseInt(e.target.value) || 0)
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Action</label>
                  <select
                    value={step.action}
                    onChange={(e) => updateStep(i, "action", e.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  >
                    <option value="invite_to_apply">Invite to Apply</option>
                    <option value="send_forms">Send Forms</option>
                    <option value="followup">Follow-up</option>
                  </select>
                </div>
              </div>
              <div className="mt-3">
                <label className="text-xs text-slate-500">Subject</label>
                <input
                  value={step.subject}
                  onChange={(e) => updateStep(i, "subject", e.target.value)}
                  required
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                />
              </div>
              <div className="mt-3">
                <label className="text-xs text-slate-500">Body</label>
                <textarea
                  value={step.body}
                  onChange={(e) => updateStep(i, "body", e.target.value)}
                  required
                  rows={4}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                />
              </div>
            </div>
          ))}

          <button
            type="button"
            onClick={addStep}
            className="w-full rounded-md border-2 border-dashed border-slate-300 py-2 text-sm text-slate-500 hover:border-blue-300 hover:text-blue-600"
          >
            + Add Step
          </button>
        </div>

        {error && (
          <p className="rounded-md bg-red-50 p-3 text-sm text-red-600">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Creating..." : "Create Sequence"}
          </button>
        </div>
      </form>
    </div>
  );
}
