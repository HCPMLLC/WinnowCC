"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { parseApiError } from "../../lib/api-error";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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

const CONTACT_ROLES = ["Purchaser", "Hiring Manager", "Prime Contractor"];

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800",
  inactive: "bg-slate-100 text-slate-800",
  prospect: "bg-blue-100 text-blue-800",
};

const EMPTY_CONTACT: ContactEntry = { first_name: "", last_name: "", email: "", phone: "", role: "" };

function getClientContacts(c: Client): ContactEntry[] {
  if (c.contacts && c.contacts.length > 0) return c.contacts;
  if (c.contact_name || c.contact_email || c.contact_phone) {
    const parts = (c.contact_name || "").split(" ");
    return [{ first_name: parts[0] || "", last_name: parts.slice(1).join(" ") || "", email: c.contact_email || "", phone: c.contact_phone || "", role: c.contact_title || "" }];
  }
  return [];
}

export default function RecruiterClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [vehicleFilter, setVehicleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [sortBy, setSortBy] = useState("company_name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    company_name: "",
    industry: "",
    website: "",
    contract_type: "",
    fee_percentage: "",
    notes: "",
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

  async function fetchClients() {
    try {
      const url = new URL(`${API_BASE}/api/recruiter/clients`);
      if (statusFilter) url.searchParams.set("status", statusFilter);
      if (vehicleFilter) url.searchParams.set("contract_vehicle", vehicleFilter);
      if (debouncedSearch) url.searchParams.set("search", debouncedSearch);
      if (sortBy) url.searchParams.set("sort_by", sortBy);
      if (sortDir) url.searchParams.set("sort_dir", sortDir);
      const res = await fetch(url.toString(), { credentials: "include" });
      if (res.ok) setClients(await res.json());
    } catch {
      /* ignore */
    }
  }

  // Debounce search input
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  useEffect(() => {
    setLoading(true);
    fetchClients().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, vehicleFilter, debouncedSearch, sortBy, sortDir]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError("");
    const body: Record<string, unknown> = { company_name: form.company_name };
    if (form.industry) body.industry = form.industry;
    if (form.website) body.website = form.website;
    if (form.contract_type) body.contract_type = form.contract_type;
    if (form.fee_percentage) body.fee_percentage = parseFloat(form.fee_percentage);
    if (form.notes) body.notes = form.notes;
    if (form.parent_client_id) body.parent_client_id = parseInt(form.parent_client_id);
    if (form.contract_vehicle) body.contract_vehicle = form.contract_vehicle;

    const nonEmpty = contacts.filter((c) => c.first_name || c.last_name || c.email || c.phone || c.role);
    if (nonEmpty.length > 0) body.contacts = nonEmpty;

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/clients`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowForm(false);
        setForm({ company_name: "", industry: "", website: "", contract_type: "", fee_percentage: "", notes: "", parent_client_id: "", contract_vehicle: "" });
        setContacts([{ ...EMPTY_CONTACT }]);
        fetchClients();
      } else {
        const data = await res.json();
        setError(parseApiError(data, "Failed to create client"));
      }
    } catch {
      setError("Network error");
    } finally {
      setCreating(false);
    }
  }

  const inputCls = "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Clients</h1>
          <p className="mt-1 text-slate-600">Manage your client companies and contracts</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          {showForm ? "Cancel" : "+ Add Client"}
        </button>
      </div>

      {showForm && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">New Client</h2>
          {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Company Name *</label>
                <input type="text" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} className={inputCls} />
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
                <input type="number" step="0.1" value={form.fee_percentage} onChange={(e) => setForm({ ...form, fee_percentage: e.target.value })} className={inputCls} placeholder="e.g. 20" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Website</label>
                <input type="url" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} className={inputCls} />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Parent Client</label>
                <select value={form.parent_client_id} onChange={(e) => setForm({ ...form, parent_client_id: e.target.value })} className={inputCls}>
                  <option value="">None (top-level)</option>
                  {clients.filter(c => !c.parent_client_id).map((c) => (
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
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} className={inputCls} />
            </div>
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setShowForm(false)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="submit" disabled={creating} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">{creating ? "Creating..." : "Create Client"}</button>
            </div>
          </form>
        </div>
      )}

      {/* Search, sort, and status filter */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, industry, contact, vehicle..."
          className="w-72 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        />
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            <option value="company_name">Sort: Client Name</option>
            <option value="industry">Sort: Industry</option>
            <option value="contract_vehicle">Sort: Contract Vehicle</option>
            <option value="status">Sort: Status</option>
            <option value="created_at">Sort: Date Added</option>
          </select>
          <button
            onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm hover:bg-slate-50"
            title={sortDir === "asc" ? "Ascending" : "Descending"}
          >
            {sortDir === "asc" ? "\u2191" : "\u2193"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {["", "active", "inactive", "prospect"].map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${statusFilter === s ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {s || "All"}
            </button>
          ))}
        </div>
      </div>

      {/* Contract vehicle filter */}
      {(() => {
        const vehicles = [...new Set(clients.map(c => c.contract_vehicle).filter(Boolean))] as string[];
        if (vehicles.length === 0) return null;
        return (
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-500">Contract Vehicle:</span>
            <button onClick={() => setVehicleFilter("")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${!vehicleFilter ? "bg-blue-600 text-white" : "bg-blue-50 text-blue-700 hover:bg-blue-100"}`}>
              All
            </button>
            {vehicles.map((v) => (
              <button key={v} onClick={() => setVehicleFilter(v)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${vehicleFilter === v ? "bg-blue-600 text-white" : "bg-blue-50 text-blue-700 hover:bg-blue-100"}`}>
                {v}
              </button>
            ))}
          </div>
        );
      })()}

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => <div key={i} className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white" />)}
        </div>
      ) : clients.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-xl font-semibold text-slate-900">No clients yet</h3>
          <p className="mt-2 text-slate-600">Add your first client to start managing engagements.</p>
          <button onClick={() => setShowForm(true)} className="mt-4 rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white hover:bg-slate-800">Add Your First Client</button>
        </div>
      ) : (
        <div className="space-y-4">
          {clients.map((c) => {
            const clientContacts = getClientContacts(c);
            const primaryContact = clientContacts[0];
            return (
              <Link key={c.id} href={`/recruiter/clients/${c.id}`}>
                <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md ${c.parent_client_id ? "ml-8 border-l-4 border-l-slate-300" : ""}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="mb-1 flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-slate-900">{c.company_name}</h3>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[c.status] ?? "bg-slate-100 text-slate-600"}`}>{c.status}</span>
                        {c.contract_vehicle && (
                          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                            {c.contract_vehicle}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm text-slate-500">
                        {c.parent_company_name && <span className="text-slate-400">Under: {c.parent_company_name}</span>}
                        {c.industry && <span>{c.industry}</span>}
                        {(primaryContact?.first_name || primaryContact?.last_name) && <span>{[primaryContact.first_name, primaryContact.last_name].filter(Boolean).join(" ")}{primaryContact.role ? ` (${primaryContact.role})` : ""}</span>}
                        {clientContacts.length > 1 && <span>+{clientContacts.length - 1} more contact{clientContacts.length > 2 ? "s" : ""}</span>}
                        {c.contract_type && <span className="capitalize">{c.contract_type.replace("_", " ")}</span>}
                        {c.fee_percentage && <span>{c.fee_percentage}% fee</span>}
                      </div>
                      <div className="mt-2 flex gap-4 text-sm text-slate-500">
                        <span className="font-medium text-slate-700">{c.job_count} job{c.job_count !== 1 ? "s" : ""}</span>
                        <span>Added {new Date(c.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <svg className="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
