"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type Suggestion = {
  id: number;
  title: string;
  description: string;
  category: string;
  source: string;
  priority_label: string | null;
  priority_score: number | null;
  status: string;
  created_at: string | null;
};

type ListResponse = {
  suggestions: Suggestion[];
  total: number;
  high_priority_count: number;
  awaiting_approval_count: number;
};

const CATEGORY_COLORS: Record<string, string> = {
  feature: "bg-blue-100 text-blue-700",
  improvement: "bg-emerald-100 text-emerald-700",
  bug: "bg-red-100 text-red-700",
  ux: "bg-purple-100 text-purple-700",
  performance: "bg-amber-100 text-amber-700",
};

const PRIORITY_COLORS: Record<string, string> = {
  HIGH: "bg-red-100 text-red-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  LOW: "bg-slate-100 text-slate-600",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  scored: "bg-blue-100 text-blue-700",
  prompt_ready: "bg-emerald-100 text-emerald-700",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-700",
};

const STATUS_TABS = ["all", "pending", "scored", "prompt_ready", "approved", "rejected"];

export default function AdminSuggestionsPage() {
  const router = useRouter();
  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formCategory, setFormCategory] = useState("feature");
  const [submitting, setSubmitting] = useState(false);

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const loadSuggestions = async () => {
      try {
        const params = activeTab && activeTab !== "all" ? `?status=${activeTab}` : "";
        const res = await fetch(`${apiBase}/api/admin/suggestions${params}`, {
          credentials: "include",
        });
        if (res.status === 401) { router.push("/login"); return; }
        if (res.status === 403) { setError("Admin access required."); return; }
        if (!res.ok) throw new Error("Failed to load suggestions.");
        setData(await res.json());
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load suggestions.");
      }
    };
    void loadSuggestions();
  }, [activeTab, apiBase, router, reloadKey]);

  const handleCreate = async () => {
    if (!formTitle.trim() || !formDesc.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${apiBase}/api/admin/suggestions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ title: formTitle, description: formDesc, category: formCategory }),
      });
      if (!res.ok) throw new Error("Failed to create suggestion.");
      setFormTitle("");
      setFormDesc("");
      setFormCategory("feature");
      setShowForm(false);
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create suggestion.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Suggestions</h1>
          <p className="text-sm text-slate-600">
            Product ideas, feature requests, and improvement suggestions from Sieve conversations.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          {showForm ? "Cancel" : "New Suggestion"}
        </button>
      </header>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-center">
            <div className="text-2xl font-bold text-slate-900">{data.total}</div>
            <div className="text-xs text-slate-500">Total</div>
          </div>
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-center">
            <div className="text-2xl font-bold text-red-700">{data.high_priority_count}</div>
            <div className="text-xs text-red-600">High Priority</div>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-center">
            <div className="text-2xl font-bold text-emerald-700">{data.awaiting_approval_count}</div>
            <div className="text-xs text-emerald-600">Awaiting Approval</div>
          </div>
        </div>
      )}

      {/* New suggestion form */}
      {showForm && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">New Suggestion</h2>
          <div className="flex flex-col gap-3">
            <input
              type="text"
              placeholder="Title"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Description — what should be built/fixed and why?"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              rows={3}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
            <select
              value={formCategory}
              onChange={(e) => setFormCategory(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="feature">Feature</option>
              <option value="improvement">Improvement</option>
              <option value="bug">Bug</option>
              <option value="ux">UX</option>
              <option value="performance">Performance</option>
            </select>
            <button
              onClick={handleCreate}
              disabled={submitting || !formTitle.trim() || !formDesc.trim()}
              className="self-start rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? "Creating..." : "Create Suggestion"}
            </button>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 overflow-x-auto">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-full px-4 py-1.5 text-xs font-semibold capitalize transition-colors ${
              activeTab === tab
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {tab.replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Suggestions list */}
      {data && data.suggestions.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
          No suggestions found.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {data?.suggestions.map((s) => (
            <Link
              key={s.id}
              href={`/admin/suggestions/${s.id}`}
              className="group rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-sm font-semibold text-slate-900 group-hover:text-blue-700">
                      {s.title}
                    </h3>
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${CATEGORY_COLORS[s.category] ?? "bg-slate-100 text-slate-600"}`}>
                      {s.category}
                    </span>
                    {s.priority_label && (
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${PRIORITY_COLORS[s.priority_label] ?? ""}`}>
                        {s.priority_label}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">{s.description}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_COLORS[s.status] ?? "bg-slate-100 text-slate-600"}`}>
                    {s.status.replace("_", " ")}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {s.source === "sieve_detected" ? "Sieve" : "Manual"}
                  </span>
                  {s.created_at && (
                    <span className="text-[10px] text-slate-400">
                      {new Date(s.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
