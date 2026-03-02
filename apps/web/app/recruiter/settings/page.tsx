"use client";

import { useEffect, useState } from "react";
import { parseApiError } from "../../lib/api-error";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface RecruiterProfile {
  id: number;
  company_name: string;
  company_type: string | null;
  company_website: string | null;
  specializations: string[] | null;
  subscription_tier: string;
  subscription_status: string | null;
  seats_purchased: number;
  seats_used: number;
  auto_populate_pipeline: boolean;
}

interface TeamMember {
  id: number;
  user_id: number;
  role: string | null;
  email: string | null;
  invited_at: string | null;
  accepted_at: string | null;
}

export default function RecruiterSettings() {
  const [profile, setProfile] = useState<RecruiterProfile | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    company_name: "",
    company_type: "",
    company_website: "",
  });

  const [autoPopulate, setAutoPopulate] = useState(false);
  const [savingPipeline, setSavingPipeline] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/recruiter/profile`, { credentials: "include" }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE}/api/recruiter/team`, { credentials: "include" }).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([p, t]) => {
        setProfile(p);
        setTeam(t || []);
        if (p) {
          setForm({
            company_name: p.company_name || "",
            company_type: p.company_type || "",
            company_website: p.company_website || "",
          });
          setAutoPopulate(p.auto_populate_pipeline ?? false);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    if (!form.company_name.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/profile`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) setProfile(await res.json());
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleAutoPopulate(newValue: boolean) {
    setSavingPipeline(true);
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/profile`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_populate_pipeline: newValue }),
      });
      if (res.ok) {
        setAutoPopulate(newValue);
        setProfile(await res.json());
      }
    } catch {
      /* ignore */
    } finally {
      setSavingPipeline(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    setInviteError("");
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/team`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      if (res.ok) {
        const member = await res.json();
        setTeam([...team, member]);
        setInviteEmail("");
      } else {
        const data = await res.json();
        setInviteError(parseApiError(data, "Failed to invite member"));
      }
    } catch {
      setInviteError("Network error");
    } finally {
      setInviting(false);
    }
  }

  async function handleRemoveMember(id: number) {
    if (!confirm("Remove this team member?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/team/${id}`, { method: "DELETE", credentials: "include" });
      if (res.ok) setTeam(team.filter((m) => m.id !== id));
    } catch {
      /* ignore */
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center py-20"><div className="text-sm text-slate-500">Loading settings...</div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Manage your recruiter account, team, and billing</p>
      </div>

      {/* Profile Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Company Profile</h2>
        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Company Name</label>
              <input type="text" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Company Type</label>
              <select value={form.company_type} onChange={(e) => setForm({ ...form, company_type: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500">
                <option value="">Select...</option>
                <option value="staffing_agency">Staffing Agency</option>
                <option value="executive_search">Executive Search</option>
                <option value="contingency">Contingency</option>
                <option value="retained_search">Retained Search</option>
                <option value="rpo">RPO</option>
                <option value="independent">Independent</option>
              </select>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Website</label>
            <input type="url" value={form.company_website} onChange={(e) => setForm({ ...form, company_website: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
          </div>
          <div className="flex justify-end">
            <button type="submit" disabled={saving} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{saving ? "Saving..." : "Save Profile"}</button>
          </div>
        </form>
      </div>

      {/* Pipeline Preferences */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Pipeline Preferences</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-700">Auto-populate pipeline</p>
            <p className="text-sm text-slate-500">Automatically add matched candidates to your pipeline when matches are computed</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={autoPopulate}
            disabled={savingPipeline}
            onClick={() => handleToggleAutoPopulate(!autoPopulate)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 disabled:opacity-50 ${autoPopulate ? "bg-slate-900" : "bg-slate-200"}`}
          >
            <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${autoPopulate ? "translate-x-5" : "translate-x-0"}`} />
          </button>
        </div>
      </div>

      {/* Team Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Team Members</h2>
          <span className="text-sm text-slate-500">{profile?.seats_used ?? 1} / {profile?.seats_purchased ?? 1} seats used</span>
        </div>

        {team.length > 0 && (
          <div className="mb-4 space-y-2">
            {team.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-700">{m.email || `User #${m.user_id}`}</p>
                  <p className="text-xs text-slate-400 capitalize">{m.role || "member"}{m.accepted_at ? "" : " (pending)"}</p>
                </div>
                <button onClick={() => handleRemoveMember(m.id)} className="text-xs text-red-500 hover:text-red-700">Remove</button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleInvite} className="flex items-end gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium text-slate-700">Invite by Email</label>
            <input type="email" required value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" placeholder="colleague@company.com" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Role</label>
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500">
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button type="submit" disabled={inviting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{inviting ? "..." : "Invite"}</button>
        </form>
        {inviteError && <p className="mt-2 text-sm text-red-600">{inviteError}</p>}
      </div>

      {/* Billing Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Billing</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-500">Current Plan</p>
            <p className="mt-1 text-xl font-bold capitalize text-slate-900">{profile?.subscription_tier ?? "trial"}</p>
            {profile?.subscription_status && (
              <p className="text-sm capitalize text-slate-500">Status: {profile.subscription_status}</p>
            )}
          </div>
          <a href="/recruiter/pricing" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800">
            {profile?.subscription_tier === "trial" ? "Choose a Plan" : "Upgrade Plan"}
          </a>
        </div>
      </div>
    </div>
  );
}
