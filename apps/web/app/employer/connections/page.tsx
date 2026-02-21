"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const BOARD_TYPES = [
  { value: "indeed", label: "Indeed", needsKey: true },
  { value: "google_jobs", label: "Google for Jobs", needsKey: false },
  { value: "ziprecruiter", label: "ZipRecruiter", needsKey: true },
  { value: "glassdoor", label: "Glassdoor", needsKey: true },
  { value: "linkedin", label: "LinkedIn", needsKey: true },
  { value: "usajobs", label: "USAJobs", needsKey: true },
  { value: "custom", label: "XML Feed", needsKey: false },
];

interface BoardConnection {
  id: number;
  board_type: string;
  board_name: string;
  feed_url: string | null;
  is_active: boolean;
  config: Record<string, unknown> | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-800",
  partial: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
};

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<BoardConnection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  // Form state
  const [boardType, setBoardType] = useState("");
  const [boardName, setBoardName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{
    valid: boolean;
    message: string;
  } | null>(null);

  async function fetchConnections() {
    try {
      const res = await fetch(`${API_BASE}/api/distribution/connections`, {
        credentials: "include",
      });
      if (res.ok) {
        setConnections(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch connections:", err);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchConnections();
  }, []);

  function resetForm() {
    setBoardType("");
    setBoardName("");
    setApiKey("");
    setApiSecret("");
    setFeedUrl("");
    setShowAddForm(false);
    setEditingId(null);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);

    try {
      const body: Record<string, unknown> = {
        board_name: boardName,
      };

      if (editingId) {
        // Update
        if (apiKey) body.api_key = apiKey;
        if (apiSecret) body.api_secret = apiSecret;
        if (feedUrl) body.feed_url = feedUrl;
        const res = await fetch(
          `${API_BASE}/api/distribution/connections/${editingId}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            credentials: "include",
          },
        );
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || "Failed to update connection");
          return;
        }
      } else {
        // Create
        body.board_type = boardType;
        if (apiKey) body.api_key = apiKey;
        if (apiSecret) body.api_secret = apiSecret;
        if (feedUrl) body.feed_url = feedUrl;
        const res = await fetch(`${API_BASE}/api/distribution/connections`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          credentials: "include",
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || "Failed to create connection");
          return;
        }
      }

      resetForm();
      fetchConnections();
    } catch (err) {
      console.error("Save failed:", err);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remove this board connection?")) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/distribution/connections/${id}`,
        { method: "DELETE", credentials: "include" },
      );
      if (res.ok) {
        setConnections((prev) => prev.filter((c) => c.id !== id));
      }
    } catch (err) {
      console.error("Delete failed:", err);
    }
  }

  async function handleTest(id: number) {
    setTestingId(id);
    setTestResult(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/distribution/connections/${id}/test`,
        { method: "POST", credentials: "include" },
      );
      if (res.ok) {
        setTestResult(await res.json());
      }
    } catch (err) {
      setTestResult({ valid: false, message: "Connection test failed" });
    } finally {
      setTestingId(null);
    }
  }

  function startEdit(conn: BoardConnection) {
    setEditingId(conn.id);
    setBoardType(conn.board_type);
    setBoardName(conn.board_name);
    setFeedUrl(conn.feed_url || "");
    setApiKey("");
    setApiSecret("");
    setShowAddForm(true);
  }

  const selectedBoard = BOARD_TYPES.find((b) => b.value === boardType);

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            Board Connections
          </h1>
          <p className="mt-1 text-slate-600">
            Connect external job boards to distribute your postings
          </p>
        </div>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            + Add Connection
          </button>
        )}
      </div>

      {/* Add / Edit Form */}
      {showAddForm && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">
            {editingId ? "Edit Connection" : "Add Board Connection"}
          </h2>
          <form onSubmit={handleSave} className="space-y-4">
            {!editingId && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Board Type
                </label>
                <select
                  value={boardType}
                  onChange={(e) => {
                    setBoardType(e.target.value);
                    const board = BOARD_TYPES.find(
                      (b) => b.value === e.target.value,
                    );
                    if (board) setBoardName(board.label);
                  }}
                  required
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="">Select a board...</option>
                  {BOARD_TYPES.map((b) => (
                    <option key={b.value} value={b.value}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Display Name
              </label>
              <input
                type="text"
                value={boardName}
                onChange={(e) => setBoardName(e.target.value)}
                required
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              />
            </div>

            {selectedBoard?.needsKey && (
              <>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={editingId ? "Leave blank to keep current" : ""}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    API Secret
                  </label>
                  <input
                    type="password"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    placeholder={editingId ? "Leave blank to keep current" : ""}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  />
                </div>
              </>
            )}

            {(boardType === "custom" || editingId) && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Feed URL
                </label>
                <input
                  type="url"
                  value={feedUrl}
                  onChange={(e) => setFeedUrl(e.target.value)}
                  placeholder="https://example.com/feed.xml"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                />
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={isSaving}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {isSaving
                  ? "Saving..."
                  : editingId
                    ? "Update"
                    : "Add Connection"}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Test Result Banner */}
      {testResult && (
        <div
          className={`mb-6 rounded-lg border p-4 ${
            testResult.valid
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">
              {testResult.valid ? "Connection valid" : "Connection failed"}:{" "}
              {testResult.message}
            </p>
            <button
              onClick={() => setTestResult(null)}
              className="text-sm underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Connections List */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(2)].map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : connections.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
          <h3 className="text-xl font-semibold text-slate-900">
            No board connections
          </h3>
          <p className="mt-2 text-slate-600">
            Connect a job board to start distributing your postings.
          </p>
          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="mt-4 inline-block rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Add Your First Connection
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {connections.map((conn) => (
            <div
              key={conn.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="mb-2 flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-slate-900">
                      {conn.board_name}
                    </h3>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {conn.board_type}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        conn.is_active
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {conn.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-4 text-sm text-slate-500">
                    {conn.feed_url && (
                      <span className="truncate max-w-xs">
                        Feed: {conn.feed_url}
                      </span>
                    )}
                    {conn.last_sync_at && (
                      <span>
                        Last sync:{" "}
                        {new Date(conn.last_sync_at).toLocaleString()}
                      </span>
                    )}
                    {conn.last_sync_status && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_COLORS[conn.last_sync_status] ??
                          "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {conn.last_sync_status}
                      </span>
                    )}
                  </div>
                  {conn.last_sync_error && (
                    <p className="mt-1 text-xs text-red-600">
                      {conn.last_sync_error}
                    </p>
                  )}
                  <p className="mt-2 text-xs text-slate-400">
                    Connected {new Date(conn.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleTest(conn.id)}
                    disabled={testingId === conn.id}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {testingId === conn.id ? "Testing..." : "Test"}
                  </button>
                  <button
                    onClick={() => startEdit(conn)}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(conn.id)}
                    className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
