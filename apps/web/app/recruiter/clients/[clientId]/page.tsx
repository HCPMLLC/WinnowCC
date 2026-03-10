"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const INDUSTRIES = [
  "Aerospace & Defense",
  "Agriculture",
  "Automotive",
  "Construction",
  "Consulting",
  "Consumer Goods",
  "Education",
  "Energy & Utilities",
  "Entertainment & Media",
  "Financial Services",
  "Food & Beverage",
  "Government",
  "Healthcare",
  "Hospitality & Tourism",
  "Insurance",
  "Legal",
  "Logistics & Transportation",
  "Manufacturing",
  "Mining & Metals",
  "Nonprofit",
  "Pharmaceuticals",
  "Professional Services",
  "Real Estate",
  "Retail & E-Commerce",
  "Technology",
  "Telecommunications",
  "Other",
];

const CONTACT_ROLES = ["Purchaser", "Hiring Manager", "Prime Contractor", "Subcontractor"];

interface ContactEntry {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: string;
}

interface Client {
  id: number;
  company_name: string;
  industry: string | null;
  company_size: string | null;
  website: string | null;
  contacts: ContactEntry[] | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  contact_title: string | null;
  contract_type: string | null;
  fee_percentage: number | null;
  flat_fee: number | null;
  notes: string | null;
  status: string;
  job_count: number;
  created_at: string;
  parent_client_id: number | null;
  contract_vehicle: string | null;
  parent_company_name: string | null;
}

interface ClientOption {
  id: number;
  company_name: string;
  parent_client_id: number | null;
}

interface Activity {
  id: number;
  activity_type: string;
  subject: string | null;
  body: string | null;
  created_at: string;
}

interface JobSummaryItem {
  id: number;
  title: string;
  status: string;
  job_id_external: string | null;
  closes_at: string | null;
  contact_name: string | null;
  contact_email: string | null;
  positions_to_fill: number;
  positions_filled: number;
}

interface ClientJobGroup {
  client_id: number;
  client_name: string;
  is_self: boolean;
  jobs_by_status: Record<string, JobSummaryItem[]>;
  total_jobs: number;
}

interface ContactJobGroup {
  contact_name: string;
  contact_email: string | null;
  jobs: JobSummaryItem[];
  total_jobs: number;
}

interface JobSummary {
  client_id: number;
  client_name: string;
  groups: ClientJobGroup[];
  by_contact: ContactJobGroup[];
  total_jobs: number;
}

const EMPTY_CONTACT: ContactEntry = { first_name: "", last_name: "", email: "", phone: "", role: "" };

function getClientContacts(c: Client): ContactEntry[] {
  if (c.contacts && c.contacts.length > 0) return c.contacts;
  if (c.contact_name || c.contact_email || c.contact_phone) {
    const parts = (c.contact_name || "").split(" ");
    return [{ first_name: parts[0] || "", last_name: parts.slice(1).join(" ") || "", email: c.contact_email || "", phone: c.contact_phone || "", role: c.contact_title || "" }];
  }
  return [];
}

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clientId = params.clientId as string;

  const [client, setClient] = useState<Client | null>(null);
  const [allClients, setAllClients] = useState<ClientOption[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [jobSummary, setJobSummary] = useState<JobSummary | null>(null);
  const [jobTab, setJobTab] = useState<"by_client" | "by_contact">("by_client");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    company_name: "",
    industry: "",
    contract_type: "",
    fee_percentage: "",
    notes: "",
    status: "",
    parent_client_id: "",
    contract_vehicle: "",
  });
  const [contacts, setContacts] = useState<ContactEntry[]>([{ ...EMPTY_CONTACT }]);

  function updateContact(idx: number, field: keyof ContactEntry, value: string) {
    setContacts(contacts.map((c, i) => (i === idx ? { ...c, [field]: value } : c)));
  }

  function addContact() {
    if (contacts.length < 10) setContacts([...contacts, { ...EMPTY_CONTACT }]);
  }

  function removeContact(idx: number) {
    if (contacts.length > 1) setContacts(contacts.filter((_, i) => i !== idx));
  }

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      fetch(`${API_BASE}/api/recruiter/clients/${clientId}`, { credentials: "include" }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE}/api/recruiter/activities?client_id=${clientId}&limit=20`, { credentials: "include" }).then((r) => (r.ok ? r.json() : [])),
      fetch(`${API_BASE}/api/recruiter/clients`, { credentials: "include" }).then((r) => (r.ok ? r.json() : [])),
      fetch(`${API_BASE}/api/recruiter/clients/${clientId}/job-summary`, { credentials: "include" }).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([c, acts, allC, js]) => {
        setClient(c);
        setActivities(acts || []);
        setJobSummary(js);
        setAllClients((allC || []).filter((cl: ClientOption) => cl.id !== parseInt(clientId)));
        if (c) {
          setForm({
            company_name: c.company_name || "",
            industry: c.industry || "",
            contract_type: c.contract_type || "",
            fee_percentage: c.fee_percentage?.toString() || "",
            notes: c.notes || "",
            status: c.status || "active",
            parent_client_id: c.parent_client_id?.toString() || "",
            contract_vehicle: c.contract_vehicle || "",
          });
          const existing = getClientContacts(c);
          setContacts(existing.length > 0 ? existing : [{ ...EMPTY_CONTACT }]);
        }
      })
      .finally(() => setLoading(false));
  }, [clientId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const body: Record<string, unknown> = {};
    if (form.company_name) body.company_name = form.company_name;
    if (form.industry) body.industry = form.industry;
    if (form.contract_type) body.contract_type = form.contract_type;
    if (form.fee_percentage) body.fee_percentage = parseFloat(form.fee_percentage);
    body.notes = form.notes;
    body.status = form.status;
    body.parent_client_id = form.parent_client_id ? parseInt(form.parent_client_id) : null;
    body.contract_vehicle = form.contract_vehicle || null;

    const nonEmpty = contacts.filter((c) => c.first_name || c.last_name || c.email || c.phone || c.role);
    body.contacts = nonEmpty;

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/clients/${clientId}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setClient(await res.json());
        setEditing(false);
      }
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure you want to delete this client?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/recruiter/clients/${clientId}`, { method: "DELETE", credentials: "include" });
      if (res.ok) router.push("/recruiter/clients");
    } catch {
      /* ignore */
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center py-20"><div className="text-sm text-slate-500">Loading client...</div></div>;
  }

  if (!client) {
    return (
      <div className="py-20 text-center">
        <h2 className="text-xl font-semibold text-slate-900">Client not found</h2>
        <Link href="/recruiter/clients" className="mt-4 inline-block text-sm text-slate-600 hover:text-slate-900">Back to Clients</Link>
      </div>
    );
  }

  const clientContacts = getClientContacts(client);
  const inputCls = "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link href="/recruiter/clients" className="mb-2 inline-block text-sm text-slate-500 hover:text-slate-700">&larr; Back to Clients</Link>
          <h1 className="text-3xl font-bold text-slate-900">{client.company_name}</h1>
          <div className="mt-1 flex items-center gap-3 text-sm text-slate-500">
            {client.industry && <span>{client.industry}</span>}
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${client.status === "active" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{client.status}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setEditing(!editing)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">{editing ? "Cancel" : "Edit"}</button>
          <button onClick={handleDelete} className="rounded-md border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-100">Delete</button>
        </div>
      </div>

      {editing ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Edit Client</h2>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Company Name</label>
                <input type="text" value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Industry</label>
                <select value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} className={inputCls}>
                  <option value="">Select industry...</option>
                  {INDUSTRIES.map((ind) => (<option key={ind} value={ind}>{ind}</option>))}
                </select>
              </div>
            </div>

            {/* Contacts */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Contacts</label>
                {contacts.length < 10 && (
                  <button type="button" onClick={addContact} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                    <span className="text-base leading-none">+</span> Add Contact
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {contacts.map((ct, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input type="text" placeholder="First Name" value={ct.first_name} onChange={(e) => updateContact(idx, "first_name", e.target.value)} className={`${inputCls} flex-1`} />
                    <input type="text" placeholder="Last Name" value={ct.last_name} onChange={(e) => updateContact(idx, "last_name", e.target.value)} className={`${inputCls} flex-1`} />
                    <input type="email" placeholder="Email" value={ct.email} onChange={(e) => updateContact(idx, "email", e.target.value)} className={`${inputCls} flex-1`} />
                    <input type="tel" placeholder="Phone" value={ct.phone} onChange={(e) => updateContact(idx, "phone", e.target.value)} className={`${inputCls} flex-1`} />
                    <select value={ct.role} onChange={(e) => updateContact(idx, "role", e.target.value)} className={`${inputCls} flex-1`}>
                      <option value="">Role...</option>
                      {CONTACT_ROLES.map((r) => (<option key={r} value={r}>{r}</option>))}
                    </select>
                    {contacts.length > 1 && (
                      <button type="button" onClick={() => removeContact(idx)} className="flex-shrink-0 text-slate-400 hover:text-red-500" title="Remove contact">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Contract Type</label>
                <select value={form.contract_type} onChange={(e) => setForm({ ...form, contract_type: e.target.value })} className={inputCls}>
                  <option value="">Select...</option>
                  <option value="contingency">Contingency</option>
                  <option value="retained">Retained</option>
                  <option value="rpo">RPO</option>
                  <option value="contract_staffing">Contract Staffing</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Fee %</label>
                <input type="number" step="0.1" value={form.fee_percentage} onChange={(e) => setForm({ ...form, fee_percentage: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className={inputCls}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="prospect">Prospect</option>
                </select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Parent Client</label>
                <select value={form.parent_client_id} onChange={(e) => setForm({ ...form, parent_client_id: e.target.value })} className={inputCls}>
                  <option value="">None (top-level)</option>
                  {allClients.filter(c => !c.parent_client_id).map((c) => (
                    <option key={c.id} value={c.id}>{c.company_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Contract Vehicle</label>
                <input type="text" value={form.contract_vehicle} onChange={(e) => setForm({ ...form, contract_vehicle: e.target.value })} className={inputCls} placeholder="e.g. DIR-CPO-TMP-445" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Notes</label>
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} className={inputCls} />
            </div>
            <div className="flex justify-end">
              <button type="submit" disabled={saving} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{saving ? "Saving..." : "Save Changes"}</button>
            </div>
          </form>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Client Details</h2>
          {(client.parent_company_name || client.contract_vehicle) && (
            <div className="mb-4 flex flex-wrap gap-3">
              {client.parent_company_name && (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                  Parent: {client.parent_company_name}
                </span>
              )}
              {client.contract_vehicle && (
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                  {client.contract_vehicle}
                </span>
              )}
            </div>
          )}
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-medium text-slate-500">Contacts</h3>
              {clientContacts.length > 0 ? (
                <div className="mt-1 space-y-2">
                  {clientContacts.map((ct, idx) => (
                    <div key={idx} className="text-sm text-slate-700">
                      <span className="font-medium">{[ct.first_name, ct.last_name].filter(Boolean).join(" ") || "—"}</span>
                      {ct.role && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{ct.role}</span>}
                      {ct.email && <p className="text-slate-500">{ct.email}</p>}
                      {ct.phone && <p className="text-slate-500">{ct.phone}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-1 text-sm text-slate-400">No contacts</p>
              )}
            </div>
            <div>
              <h3 className="text-sm font-medium text-slate-500">Contract</h3>
              <p className="mt-1 text-sm capitalize text-slate-700">{client.contract_type?.replace("_", " ") || "—"}</p>
              {client.fee_percentage && <p className="text-sm text-slate-500">{client.fee_percentage}% fee</p>}
              {client.flat_fee && <p className="text-sm text-slate-500">${client.flat_fee.toLocaleString()} flat fee</p>}
            </div>
            {client.website && (
              <div>
                <h3 className="text-sm font-medium text-slate-500">Website</h3>
                <a href={client.website} target="_blank" rel="noopener noreferrer" className="mt-1 text-sm text-blue-600 hover:underline">{client.website}</a>
              </div>
            )}
            {client.notes && (
              <div className="sm:col-span-2">
                <h3 className="text-sm font-medium text-slate-500">Notes</h3>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{client.notes}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Jobs Summary */}
      {jobSummary && jobSummary.total_jobs > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              Jobs <span className="ml-1 text-sm font-normal text-slate-500">({jobSummary.total_jobs})</span>
            </h2>
            <div className="flex rounded-lg border border-slate-200 text-sm">
              <button
                onClick={() => setJobTab("by_client")}
                className={`px-3 py-1.5 font-medium ${jobTab === "by_client" ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"} rounded-l-lg`}
              >
                By Client
              </button>
              <button
                onClick={() => setJobTab("by_contact")}
                className={`px-3 py-1.5 font-medium ${jobTab === "by_contact" ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"} rounded-r-lg`}
              >
                By Contact
              </button>
            </div>
          </div>

          {jobTab === "by_client" ? (
            <div className="space-y-4">
              {jobSummary.groups.map((group) => (
                <div key={group.client_id}>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">
                    {group.client_name}
                    {group.is_self && <span className="ml-1 text-xs font-normal text-slate-400">(this client)</span>}
                    <span className="ml-1 text-xs font-normal text-slate-500">({group.total_jobs})</span>
                  </h3>
                  {Object.entries(group.jobs_by_status).map(([st, jobs]) => (
                    <div key={st} className="mb-2 ml-2">
                      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">{st} ({jobs.length})</p>
                      <div className="space-y-1">
                        {jobs.map((job) => (
                          <Link
                            key={job.id}
                            href={`/recruiter/jobs/${job.id}/edit`}
                            className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm hover:bg-slate-50"
                          >
                            <div className="min-w-0 flex-1">
                              <span className="font-medium text-slate-800">{job.title}</span>
                              {job.job_id_external && (
                                <span className="ml-2 text-xs text-slate-400">{job.job_id_external}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-3 text-xs text-slate-500">
                              {job.contact_name && <span>{job.contact_name}</span>}
                              {job.closes_at && (
                                <span>{new Date(job.closes_at).toLocaleDateString()}</span>
                              )}
                              <span>{job.positions_filled}/{job.positions_to_fill}</span>
                            </div>
                          </Link>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {jobSummary.by_contact.length === 0 ? (
                <p className="text-sm text-slate-500">No contacts assigned to jobs.</p>
              ) : (
                jobSummary.by_contact.map((cg, idx) => (
                  <div key={idx}>
                    <h3 className="mb-2 text-sm font-semibold text-slate-700">
                      {cg.contact_name}
                      {cg.contact_email && (
                        <span className="ml-2 text-xs font-normal text-slate-400">{cg.contact_email}</span>
                      )}
                      <span className="ml-1 text-xs font-normal text-slate-500">({cg.total_jobs})</span>
                    </h3>
                    <div className="space-y-1 ml-2">
                      {cg.jobs.map((job) => (
                        <Link
                          key={job.id}
                          href={`/recruiter/jobs/${job.id}/edit`}
                          className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm hover:bg-slate-50"
                        >
                          <div className="min-w-0 flex-1">
                            <span className="font-medium text-slate-800">{job.title}</span>
                            {job.job_id_external && (
                              <span className="ml-2 text-xs text-slate-400">{job.job_id_external}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-500">
                            <span className={`rounded-full px-2 py-0.5 ${job.status === "open" ? "bg-emerald-100 text-emerald-700" : job.status === "closed" ? "bg-slate-100 text-slate-600" : "bg-amber-100 text-amber-700"}`}>
                              {job.status}
                            </span>
                            {job.closes_at && (
                              <span>{new Date(job.closes_at).toLocaleDateString()}</span>
                            )}
                            <span>{job.positions_filled}/{job.positions_to_fill}</span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Activity Feed */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Recent Activity</h2>
        {activities.length === 0 ? (
          <p className="text-sm text-slate-500">No activity recorded for this client yet.</p>
        ) : (
          <div className="space-y-3">
            {activities.map((a) => (
              <div key={a.id} className="flex items-start gap-3 border-l-2 border-slate-200 pl-4">
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-700">{a.subject || a.activity_type}</p>
                  {a.body && <p className="mt-0.5 text-sm text-slate-500">{a.body}</p>}
                  <p className="mt-0.5 text-xs text-slate-400">{new Date(a.created_at).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
