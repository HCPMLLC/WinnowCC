"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchAuthMe } from "../../lib/auth";
import CandidateLayout from "../../components/CandidateLayout";

const API =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Reference = {
  id: string;
  name: string;
  title?: string | null;
  company: string;
  phone: string;
  email?: string | null;
  relationship: string;
  years_known?: number | null;
  notes?: string | null;
  is_active: boolean;
};

const RELATIONSHIP_OPTIONS = [
  "Peer",
  "Co-Worker",
  "Supervisor",
  "Customer",
  "End-User",
  "Subordinate",
  "Manager",
  "Mentor",
  "Direct Report",
  "Other",
];

const emptyRef = {
  name: "",
  title: "",
  company: "",
  phone: "",
  email: "",
  relationship: "Peer",
  years_known: null as number | null,
  notes: "",
};

export default function ReferencesPage() {
  const router = useRouter();
  const [refs, setRefs] = useState<Reference[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState(emptyRef);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchAuthMe().then((u) => {
      if (!u) {
        router.push("/login");
        return;
      }
      loadRefs();
    });
  }, [router]);

  async function loadRefs() {
    setLoading(true);
    const res = await fetch(`${API}/api/profile/references`, {
      credentials: "include",
    });
    if (res.ok) {
      setRefs(await res.json());
    }
    setLoading(false);
  }

  async function handleSave() {
    setSaving(true);
    const method = editing ? "PUT" : "POST";
    const url = editing
      ? `${API}/api/profile/references/${editing}`
      : `${API}/api/profile/references`;
    const body: Record<string, unknown> = { ...form };
    if (body.years_known === null || body.years_known === "") {
      delete body.years_known;
    }
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (res.ok) {
      setEditing(null);
      setForm(emptyRef);
      await loadRefs();
    }
    setSaving(false);
  }

  async function handleDelete(id: string) {
    await fetch(`${API}/api/profile/references/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    await loadRefs();
  }

  function startEdit(ref: Reference) {
    setEditing(ref.id);
    setForm({
      name: ref.name,
      title: ref.title || "",
      company: ref.company,
      phone: ref.phone,
      email: ref.email || "",
      relationship: ref.relationship,
      years_known: ref.years_known ?? null,
      notes: ref.notes || "",
    });
  }

  const activeCount = refs.filter((r) => r.is_active).length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading references...</p>
      </div>
    );
  }

  return (
    <CandidateLayout>
      <div>
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Professional References
          </h1>
          <span
            className={`text-sm font-medium px-3 py-1 rounded-full ${
              activeCount >= 3
                ? "bg-green-100 text-green-800"
                : "bg-yellow-100 text-yellow-800"
            }`}
          >
            {activeCount} of 3 references
          </span>
        </div>

        <p className="text-sm text-gray-500 mb-6">
          Many government and staffing solicitations require 3 professional
          references. Add at least 3 to maximize your application readiness.
        </p>

        {/* Reference list */}
        <div className="space-y-4 mb-8">
          {refs.map((ref) => (
            <div
              key={ref.id}
              className="bg-white rounded-lg shadow-sm border p-4"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold text-gray-900">{ref.name}</h3>
                  <p className="text-sm text-gray-600">
                    {ref.title && `${ref.title}, `}
                    {ref.company}
                  </p>
                  <p className="text-sm text-gray-500">
                    {ref.phone}
                    {ref.email && ` | ${ref.email}`}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {ref.relationship}
                    {ref.years_known && ` | ${ref.years_known} years known`}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => startEdit(ref)}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(ref.id)}
                    className="text-sm text-red-600 hover:text-red-800"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add / Edit form */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">
            {editing ? "Edit Reference" : "Add Reference"}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Full Name *
              </label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Jane Doe"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title
              </label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Senior Project Manager"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Company *
              </label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.company}
                onChange={(e) => setForm({ ...form, company: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Phone *
              </label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="(555) 123-4567"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                type="email"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Relationship *
              </label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.relationship}
                onChange={(e) =>
                  setForm({ ...form, relationship: e.target.value })
                }
              >
                {RELATIONSHIP_OPTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Years Known
              </label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                type="number"
                min={0}
                value={form.years_known ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    years_known: e.target.value
                      ? parseInt(e.target.value)
                      : null,
                  })
                }
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes
              </label>
              <textarea
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={2}
              />
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !form.name || !form.company || !form.phone}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : editing ? "Update" : "Add Reference"}
            </button>
            {editing && (
              <button
                onClick={() => {
                  setEditing(null);
                  setForm(emptyRef);
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>
    </CandidateLayout>
  );
}
