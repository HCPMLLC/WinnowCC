"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type UserSummary = {
  id: number;
  email: string;
  name: string | null;
  completeness_score: number;
  onboarding_completed: boolean;
};

type PurgeableUser = {
  id: number;
  email: string;
  name: string | null;
  reason: "test" | "inactive";
  created_at: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function CompletenessIndicator({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-emerald-600 bg-emerald-100"
      : score >= 50
        ? "text-amber-600 bg-amber-100"
        : "text-red-600 bg-red-100";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}
    >
      {score}%
    </span>
  );
}

function ReasonBadge({ reason }: { reason: "test" | "inactive" }) {
  const styles =
    reason === "test"
      ? "bg-orange-100 text-orange-700"
      : "bg-slate-100 text-slate-600";
  const label = reason === "test" ? "Test Profile" : "Inactive";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}
    >
      {label}
    </span>
  );
}

export default function AdminProfileListPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  // Selection state (shared between main table and purgeable panel)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Purge state
  const [purgeableUsers, setPurgeableUsers] = useState<PurgeableUser[] | null>(
    null,
  );
  const [purgeSelectedIds, setPurgeSelectedIds] = useState<Set<number>>(
    new Set(),
  );
  const [isScanning, setIsScanning] = useState(false);
  const [isPurging, setIsPurging] = useState(false);
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);

  // Delete state
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Merge state
  const [isMerging, setIsMerging] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [primaryUserId, setPrimaryUserId] = useState<number | null>(null);

  const loadUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/api/admin/profile/users`, {
        credentials: "include",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 403) {
        setError("Admin access required.");
        return;
      }
      if (!response.ok) {
        throw new Error("Failed to load users.");
      }
      const payload = (await response.json()) as UserSummary[];
      setUsers(payload);
      setSelectedIds(new Set());
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to load users.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  // Filter users by search term
  const filteredUsers = users.filter((u) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      u.name?.toLowerCase().includes(term) ||
      u.email?.toLowerCase().includes(term)
    );
  });

  // --- Main table selection ---
  const toggleUserSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllUsers = () => {
    if (selectedIds.size === filteredUsers.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredUsers.map((u) => u.id)));
    }
  };

  // --- Delete selected ---
  const handleDelete = async () => {
    setShowDeleteConfirm(false);
    setIsDeleting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/profile/purge`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_ids: Array.from(selectedIds) }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(
          (body as { detail?: string } | null)?.detail ?? "Delete failed.",
        );
      }
      const result = (await response.json()) as {
        deleted_count: number;
        message: string;
      };
      setSuccessMsg(result.message);
      setSelectedIds(new Set());
      void loadUsers();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Delete failed.";
      setError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  // --- Merge selected ---
  const handleMerge = async () => {
    if (selectedIds.size < 2 || !primaryUserId) return;

    const duplicateIds = Array.from(selectedIds).filter(
      (id) => id !== primaryUserId,
    );

    setIsMerging(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/admin/candidates/merge`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            primary_user_id: primaryUserId,
            duplicate_user_ids: duplicateIds,
          }),
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(
          (body as { detail?: string } | null)?.detail ?? "Merge failed.",
        );
      }
      const result = (await response.json()) as { message: string };
      setSuccessMsg(result.message);
      setShowMergeModal(false);
      setPrimaryUserId(null);
      setSelectedIds(new Set());
      void loadUsers();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Merge failed.";
      setError(message);
    } finally {
      setIsMerging(false);
    }
  };

  // --- Purgeable scan ---
  const handleScan = async () => {
    setIsScanning(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/profile/purgeable`,
        { credentials: "include" },
      );
      if (!response.ok) throw new Error("Failed to scan for purgeable users.");
      const data = (await response.json()) as PurgeableUser[];
      setPurgeableUsers(data);
      setPurgeSelectedIds(new Set(data.map((u) => u.id)));
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Scan failed.";
      setError(message);
    } finally {
      setIsScanning(false);
    }
  };

  const handlePurge = async () => {
    setShowPurgeConfirm(false);
    setIsPurging(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/profile/purge`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_ids: Array.from(purgeSelectedIds) }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(
          (body as { detail?: string } | null)?.detail ?? "Purge failed.",
        );
      }
      const result = (await response.json()) as {
        deleted_count: number;
        message: string;
      };
      setSuccessMsg(result.message);
      setPurgeableUsers(null);
      setPurgeSelectedIds(new Set());
      void loadUsers();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Purge failed.";
      setError(message);
    } finally {
      setIsPurging(false);
    }
  };

  const togglePurgeId = (id: number) => {
    setPurgeSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAllPurge = () => {
    if (!purgeableUsers) return;
    if (purgeSelectedIds.size === purgeableUsers.length) {
      setPurgeSelectedIds(new Set());
    } else {
      setPurgeSelectedIds(new Set(purgeableUsers.map((u) => u.id)));
    }
  };

  // Selected user details for merge modal
  const selectedUsers = users.filter((u) => selectedIds.has(u.id));

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
      <header className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold">User Profiles</h1>
          <p className="text-sm text-slate-600">
            {users.length} total users. View and edit candidate profiles.
          </p>
        </div>
        <button
          onClick={handleScan}
          disabled={isScanning}
          className="shrink-0 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isScanning ? "Scanning..." : "Scan for Purgeable Profiles"}
        </button>
      </header>

      {successMsg ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {successMsg}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {/* Purgeable preview panel */}
      {purgeableUsers !== null ? (
        <div className="rounded-3xl border border-amber-200 bg-amber-50 shadow-sm">
          <div className="flex items-center justify-between border-b border-amber-200 px-6 py-4">
            <div>
              <h2 className="text-sm font-semibold text-amber-900">
                Purgeable Profiles ({purgeableUsers.length})
              </h2>
              <p className="text-xs text-amber-700">
                {purgeSelectedIds.size} selected for deletion
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={toggleAllPurge}
                className="text-xs font-medium text-amber-800 underline hover:text-amber-950"
              >
                {purgeSelectedIds.size === purgeableUsers.length
                  ? "Deselect all"
                  : "Select all"}
              </button>
              <button
                onClick={() => setPurgeableUsers(null)}
                className="text-xs font-medium text-slate-500 hover:text-slate-700"
              >
                Dismiss
              </button>
            </div>
          </div>

          {purgeableUsers.length === 0 ? (
            <div className="px-6 py-4 text-sm text-amber-700">
              No purgeable profiles found.
            </div>
          ) : (
            <>
              <table className="w-full">
                <tbody className="divide-y divide-amber-100">
                  {purgeableUsers.map((u) => (
                    <tr key={u.id} className="hover:bg-amber-100/50">
                      <td className="w-10 px-6 py-3">
                        <input
                          type="checkbox"
                          checked={purgeSelectedIds.has(u.id)}
                          onChange={() => togglePurgeId(u.id)}
                          className="h-4 w-4 rounded border-amber-300 text-amber-600 focus:ring-amber-500"
                        />
                      </td>
                      <td className="py-3">
                        <div className="text-sm font-medium text-slate-900">
                          {u.name || "No name"}
                        </div>
                        <div className="text-xs text-slate-500">{u.email}</div>
                      </td>
                      <td className="px-6 py-3">
                        <ReasonBadge reason={u.reason} />
                      </td>
                      <td className="px-6 py-3 text-right text-xs text-slate-500">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="flex justify-end border-t border-amber-200 px-6 py-4">
                <button
                  onClick={() => setShowPurgeConfirm(true)}
                  disabled={purgeSelectedIds.size === 0 || isPurging}
                  className="rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {isPurging
                    ? "Purging..."
                    : `Purge ${purgeSelectedIds.size} Profile${purgeSelectedIds.size !== 1 ? "s" : ""}`}
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {/* Purge Confirmation dialog */}
      {showPurgeConfirm ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">
              Confirm Purge
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              This will permanently delete{" "}
              <span className="font-semibold">{purgeSelectedIds.size}</span>{" "}
              user{purgeSelectedIds.size !== 1 ? "s" : ""} and all associated data.
              This cannot be undone.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowPurgeConfirm(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handlePurge}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Yes, Purge
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Search and Actions bar */}
      <div className="flex flex-wrap items-center gap-4">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by name or email..."
          className="w-full max-w-md rounded-xl border border-slate-200 px-4 py-2 text-sm"
        />
        {searchTerm && (
          <span className="text-sm text-slate-500">
            {filteredUsers.length} result{filteredUsers.length !== 1 ? "s" : ""}
          </span>
        )}

        <div className="ml-auto flex gap-2">
          {selectedIds.size >= 2 && (
            <button
              type="button"
              onClick={() => {
                setPrimaryUserId(Array.from(selectedIds)[0]);
                setShowMergeModal(true);
              }}
              className="rounded-full bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
            >
              Merge Selected ({selectedIds.size})
            </button>
          )}
          {selectedIds.size > 0 && (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={isDeleting}
              className="rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
            >
              {isDeleting
                ? "Deleting..."
                : `Delete Selected (${selectedIds.size})`}
            </button>
          )}
        </div>
      </div>

      {/* Delete Confirmation dialog */}
      {showDeleteConfirm ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">
              Confirm Delete
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              This will permanently delete{" "}
              <span className="font-semibold">{selectedIds.size}</span>{" "}
              user{selectedIds.size !== 1 ? "s" : ""} and all associated data
              (profiles, resumes, matches, tailored resumes, etc.). This cannot
              be undone.
            </p>
            <div className="mt-4 max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
              {selectedUsers.map((u) => (
                <div key={u.id} className="py-1 text-sm text-slate-700">
                  {u.name || "No name"}{" "}
                  <span className="text-slate-400">({u.email})</span>
                </div>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Merge Modal */}
      {showMergeModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">
              Merge Profiles
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Select the primary profile to keep. All data from the other{" "}
              {selectedIds.size - 1} profile{selectedIds.size - 1 !== 1 ? "s" : ""}{" "}
              will be transferred to the primary, and the duplicates will be
              deleted.
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {selectedUsers.map((u) => (
                <label
                  key={u.id}
                  className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition-colors ${
                    primaryUserId === u.id
                      ? "border-amber-400 bg-amber-50"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="primary_user"
                    checked={primaryUserId === u.id}
                    onChange={() => setPrimaryUserId(u.id)}
                    className="h-4 w-4 text-amber-600 focus:ring-amber-500"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-900">
                      {u.name || "No name"}
                    </div>
                    <div className="text-xs text-slate-500">{u.email}</div>
                  </div>
                  <CompletenessIndicator score={u.completeness_score} />
                  {primaryUserId === u.id && (
                    <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-800">
                      Primary
                    </span>
                  )}
                </label>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowMergeModal(false);
                  setPrimaryUserId(null);
                }}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleMerge}
                disabled={!primaryUserId || isMerging}
                className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {isMerging ? "Merging..." : "Merge"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Main user table */}
      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          Loading users...
        </div>
      ) : filteredUsers.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          {searchTerm ? "No users match your search." : "No users found."}
        </div>
      ) : (
        <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                <th className="px-4 py-4">
                  <input
                    type="checkbox"
                    checked={
                      filteredUsers.length > 0 &&
                      selectedIds.size === filteredUsers.length
                    }
                    onChange={toggleSelectAllUsers}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                </th>
                <th className="px-6 py-4">User</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Completeness</th>
                <th className="px-6 py-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredUsers.map((user) => (
                <tr
                  key={user.id}
                  className={`hover:bg-slate-50 ${selectedIds.has(user.id) ? "bg-slate-50" : ""}`}
                >
                  <td className="px-4 py-4">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(user.id)}
                      onChange={() => toggleUserSelect(user.id)}
                      className="h-4 w-4 rounded border-slate-300"
                    />
                  </td>
                  <td className="px-6 py-4">
                    <Link
                      href={`/admin/profile/${user.id}`}
                      className="text-sm font-medium text-slate-900 hover:text-slate-600 hover:underline"
                    >
                      {user.name || "No name"}
                    </Link>
                    <div className="text-xs text-slate-500">{user.email}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        user.onboarding_completed
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {user.onboarding_completed ? "Onboarded" : "Incomplete"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <CompletenessIndicator score={user.completeness_score} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      href={`/admin/profile/${user.id}`}
                      className="text-sm font-medium text-slate-600 hover:text-slate-900"
                    >
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
