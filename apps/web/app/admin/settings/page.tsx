"use client";

import { useEffect, useState, useCallback } from "react";

type TestEmailEntry = {
  email: string;
  source: "env" | "db";
  added_by: string | null;
  created_at: string | null;
};

type TestEmailsResponse = {
  env_emails: string[];
  db_emails: TestEmailEntry[];
  all_emails: string[];
};

const API =
  (typeof window !== "undefined" &&
    process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://127.0.0.1:8000";

export default function AdminSettingsPage() {
  const [data, setData] = useState<TestEmailsResponse | null>(null);
  const [newEmail, setNewEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/settings/test-emails`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(await res.text());
      setData(await res.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const addEmail = async () => {
    const email = newEmail.trim().toLowerCase();
    if (!email) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/settings/test-emails`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Error ${res.status}`);
      }
      setData(await res.json());
      setNewEmail("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setBusy(false);
    }
  };

  const removeEmail = async (email: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/settings/test-emails`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Error ${res.status}`);
      }
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Settings</h1>

      {/* Admin Test Emails */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">
          Admin Test Emails
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          These emails bypass all billing checks and see top-tier features
          without a Stripe subscription.
        </p>

        {error && (
          <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Server Config (env var — read-only) */}
        {data && data.env_emails.length > 0 && (
          <div className="mt-5">
            <h3 className="text-sm font-medium text-slate-600">
              Server Config{" "}
              <span className="font-normal text-slate-400">
                (from env var — read-only)
              </span>
            </h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {data.env_emails.map((email) => (
                <span
                  key={email}
                  className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-500"
                >
                  {email}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Dynamic emails (DB — mutable) */}
        <div className="mt-5">
          <h3 className="text-sm font-medium text-slate-600">
            Dynamic Test Emails
          </h3>
          {data && data.db_emails.length > 0 ? (
            <ul className="mt-2 divide-y divide-slate-100">
              {data.db_emails.map((entry) => (
                <li
                  key={entry.email}
                  className="flex items-center justify-between py-2"
                >
                  <div>
                    <span className="text-sm font-medium text-slate-800">
                      {entry.email}
                    </span>
                    {entry.added_by && (
                      <span className="ml-2 text-xs text-slate-400">
                        added by {entry.added_by}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => removeEmail(entry.email)}
                    disabled={busy}
                    className="rounded-md px-3 py-1 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            data && (
              <p className="mt-2 text-sm text-slate-400">
                No dynamic test emails yet.
              </p>
            )
          )}
        </div>

        {/* Add email */}
        <div className="mt-5 flex gap-2">
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void addEmail();
            }}
            placeholder="email@example.com"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
          <button
            onClick={() => void addEmail()}
            disabled={busy || !newEmail.trim()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Add
          </button>
        </div>

        {/* Active email count */}
        {data && (
          <p className="mt-4 text-xs text-slate-400">
            {data.all_emails.length} total billing-bypass email
            {data.all_emails.length !== 1 ? "s" : ""} active
          </p>
        )}
      </div>
    </div>
  );
}
