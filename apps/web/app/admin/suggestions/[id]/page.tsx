"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";

type Suggestion = {
  id: number;
  title: string;
  description: string;
  category: string;
  source: string;
  source_user_id: number | null;
  conversation_snippet: string | null;
  alignment_score: number | null;
  value_score: number | null;
  cost_estimate: string | null;
  cost_score: number | null;
  priority_score: number | null;
  priority_label: string | null;
  scoring_rationale: string | null;
  implementation_prompt: string | null;
  prompt_file_path: string | null;
  status: string;
  admin_notes: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

function ScoreBar({ label, value, max = 100 }: { label: string; value: number | null; max?: number }) {
  const pct = value != null ? Math.min((value / max) * 100, 100) : 0;
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs font-medium text-slate-600">{label}</span>
      <div className="h-2 flex-1 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-xs font-semibold text-slate-700">
        {value != null ? Math.round(value) : "—"}
      </span>
    </div>
  );
}

export default function SuggestionDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const [s, setS] = useState<Suggestion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [rejectNotes, setRejectNotes] = useState("");
  const [approveNotes, setApproveNotes] = useState("");
  const [copied, setCopied] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiBase}/api/admin/suggestions/${id}`, {
          credentials: "include",
        });
        if (res.status === 401) { router.push("/login"); return; }
        if (res.status === 403) { setError("Admin access required."); return; }
        if (!res.ok) throw new Error("Suggestion not found.");
        setS(await res.json());
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load suggestion.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [id, apiBase, router, reloadKey]);

  const doAction = async (action: string, body?: object) => {
    setActing(true);
    setError(null);
    setStatusMsg(null);
    try {
      const res = await fetch(`${apiBase}/api/admin/suggestions/${id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Action failed.`);
      }
      const data = await res.json();
      setStatusMsg(data.message || "Done.");
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed.");
    } finally {
      setActing(false);
    }
  };

  const handleCopy = () => {
    if (s?.implementation_prompt) {
      navigator.clipboard.writeText(s.implementation_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!s) {
    return (
      <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-6 py-16">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "Suggestion not found."}
        </div>
      </main>
    );
  }

  const STATUS_FLOW = ["pending", "scored", "prompt_ready", "approved"];

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-6 py-16">
      {/* Back link */}
      <button
        onClick={() => router.push("/admin/suggestions")}
        className="self-start text-xs font-medium text-slate-500 hover:text-slate-700"
      >
        &larr; Back to Suggestions
      </button>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}
      {statusMsg && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {statusMsg}
        </div>
      )}

      {/* Header */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{s.title}</h1>
            <div className="mt-2 flex items-center gap-2">
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                {s.category}
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                {s.source === "sieve_detected" ? "Sieve Detected" : "Manual Entry"}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                s.status === "approved" ? "bg-green-100 text-green-800" :
                s.status === "rejected" ? "bg-red-100 text-red-700" :
                s.status === "prompt_ready" ? "bg-emerald-100 text-emerald-700" :
                s.status === "scored" ? "bg-blue-100 text-blue-700" :
                "bg-slate-100 text-slate-600"
              }`}>
                {s.status.replace("_", " ")}
              </span>
            </div>
          </div>
          {s.priority_label && (
            <div className="text-center">
              <div className={`rounded-full px-3 py-1 text-sm font-bold ${
                s.priority_label === "HIGH" ? "bg-red-100 text-red-700" :
                s.priority_label === "MEDIUM" ? "bg-amber-100 text-amber-700" :
                "bg-slate-100 text-slate-600"
              }`}>
                {s.priority_label}
              </div>
              {s.priority_score != null && (
                <div className="mt-1 text-[10px] text-slate-500">Score: {s.priority_score}</div>
              )}
            </div>
          )}
        </div>
        <p className="mt-4 text-sm text-slate-600">{s.description}</p>
        {s.conversation_snippet && (
          <div className="mt-4 rounded-xl bg-slate-50 p-3">
            <div className="mb-1 text-[10px] font-semibold uppercase text-slate-400">Conversation Snippet</div>
            <p className="text-xs text-slate-600 italic">&ldquo;{s.conversation_snippet}&rdquo;</p>
          </div>
        )}
        {s.created_at && (
          <div className="mt-3 text-[10px] text-slate-400">
            Created {new Date(s.created_at).toLocaleString()}
            {s.updated_at && ` · Updated ${new Date(s.updated_at).toLocaleString()}`}
          </div>
        )}
      </div>

      {/* Status timeline */}
      <div className="flex items-center gap-1">
        {STATUS_FLOW.map((step, i) => {
          const currentIdx = s.status === "rejected" ? -1 : STATUS_FLOW.indexOf(s.status);
          const isComplete = i <= currentIdx;
          const isCurrent = i === currentIdx;
          return (
            <div key={step} className="flex flex-1 items-center">
              <div className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold ${
                isCurrent ? "bg-blue-600 text-white" :
                isComplete ? "bg-emerald-500 text-white" :
                "bg-slate-100 text-slate-400"
              }`}>
                {i + 1}
              </div>
              <span className={`ml-1 text-[10px] font-medium ${
                isComplete ? "text-slate-700" : "text-slate-400"
              }`}>
                {step.replace("_", " ")}
              </span>
              {i < STATUS_FLOW.length - 1 && (
                <div className={`mx-2 h-0.5 flex-1 ${
                  isComplete && i < currentIdx ? "bg-emerald-400" : "bg-slate-200"
                }`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Score bars */}
      {s.alignment_score != null && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Evaluation Scores</h2>
          <div className="flex flex-col gap-3">
            <ScoreBar label="Alignment" value={s.alignment_score} />
            <ScoreBar label="Value" value={s.value_score} />
            <ScoreBar label="Cost" value={s.cost_score} />
          </div>
          {s.cost_estimate && (
            <div className="mt-3 text-xs text-slate-500">
              Cost estimate: <span className="font-semibold">{s.cost_estimate}</span>
            </div>
          )}
          {s.scoring_rationale && (
            <div className="mt-4 rounded-xl bg-slate-50 p-3">
              <div className="mb-1 text-[10px] font-semibold uppercase text-slate-400">Rationale</div>
              <p className="text-xs text-slate-600">{s.scoring_rationale}</p>
            </div>
          )}
        </div>
      )}

      {/* Implementation prompt */}
      {s.implementation_prompt && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Implementation Prompt</h2>
            <button
              onClick={handleCopy}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-200"
            >
              {copied ? "Copied!" : "Copy Prompt"}
            </button>
          </div>
          {s.prompt_file_path && (
            <div className="mb-3 text-[10px] text-slate-400">
              Saved to: <code className="rounded bg-slate-100 px-1">{s.prompt_file_path}</code>
            </div>
          )}
          <pre className="max-h-96 overflow-auto rounded-xl bg-slate-50 p-4 text-xs text-slate-700 whitespace-pre-wrap">
            {s.implementation_prompt}
          </pre>
        </div>
      )}

      {/* Admin notes */}
      {s.admin_notes && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-1 text-[10px] font-semibold uppercase text-slate-400">Admin Notes</div>
          <p className="text-xs text-slate-600">{s.admin_notes}</p>
        </div>
      )}

      {/* Action buttons */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-slate-900">Actions</h2>
        <div className="flex flex-col gap-4">
          {s.status === "pending" && (
            <button
              onClick={() => doAction("score")}
              disabled={acting}
              className="self-start rounded-full bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {acting ? "Evaluating..." : "Run Evaluation"}
            </button>
          )}

          {s.status === "scored" && (
            <button
              onClick={() => doAction("generate-prompt")}
              disabled={acting}
              className="self-start rounded-full bg-purple-600 px-5 py-2 text-sm font-semibold text-white hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {acting ? "Generating..." : "Generate Prompt"}
            </button>
          )}

          {s.status === "prompt_ready" && (
            <div className="flex flex-col gap-3">
              <div className="flex gap-3">
                <button
                  onClick={() => doAction("approve", { admin_notes: approveNotes || null })}
                  disabled={acting}
                  className="rounded-full bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {acting ? "Approving..." : "Approve"}
                </button>
                <button
                  onClick={() => {
                    if (!rejectNotes.trim()) {
                      setError("Please provide rejection notes.");
                      return;
                    }
                    doAction("reject", { admin_notes: rejectNotes });
                  }}
                  disabled={acting}
                  className="rounded-full bg-rose-600 px-5 py-2 text-sm font-semibold text-white hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  Reject
                </button>
              </div>
              <input
                type="text"
                placeholder="Approval notes (optional)"
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
              />
              <input
                type="text"
                placeholder="Rejection notes (required to reject)"
                value={rejectNotes}
                onChange={(e) => setRejectNotes(e.target.value)}
                className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
              />
            </div>
          )}

          {s.status === "approved" && s.implementation_prompt && (
            <div className="flex items-center gap-3">
              <button
                onClick={handleCopy}
                className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white hover:bg-slate-800"
              >
                {copied ? "Copied!" : "Copy Prompt to Clipboard"}
              </button>
              <span className="text-xs text-slate-500">Paste into Claude Code when ready</span>
            </div>
          )}

          {s.status === "rejected" && (
            <p className="text-xs text-slate-500">
              Rejected{s.rejected_at ? ` on ${new Date(s.rejected_at).toLocaleDateString()}` : ""}.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
