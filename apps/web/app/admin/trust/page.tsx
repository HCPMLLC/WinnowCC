"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type TrustRecord = {
  id: number;
  resume_document_id: number;
  score: number;
  status: "allowed" | "soft_quarantine" | "hard_quarantine";
  reasons: { code: string; severity: string; message: string; points?: number }[];
  user_message: string;
  internal_notes: string | null;
  updated_at: string;
};

type TrustUpdateResponse = {
  id: number;
  status: "allowed" | "soft_quarantine" | "hard_quarantine";
  internal_notes: string | null;
};

export default function AdminTrustPage() {
  const router = useRouter();
  const [records, setRecords] = useState<TrustRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});

  useEffect(() => {
    const loadQueue = async () => {
      const apiBase =
        process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
      try {
        const response = await fetch(`${apiBase}/api/admin/trust/queue`, {
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
          throw new Error("Failed to load trust queue.");
        }
        const payload = (await response.json()) as TrustRecord[];
        setRecords(payload);
        setStatusMessage(null);
      } catch (caught) {
        const message =
          caught instanceof Error
            ? caught.message
            : "Failed to load trust queue.";
        setError(message);
      }
    };

    void loadQueue();
  }, [router]);

  const handleUpdate = async (trustId: number, newStatus: TrustRecord["status"]) => {
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
    setPendingId(trustId);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await fetch(`${apiBase}/api/admin/trust/${trustId}/set`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          status: newStatus,
          internal_notes: notes[trustId] ?? null,
        }),
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
        throw new Error("Failed to update trust status.");
      }
      const payload = (await response.json()) as TrustUpdateResponse;
      setRecords((current) =>
        current.map((record) =>
          record.id === payload.id
            ? {
                ...record,
                status: payload.status,
                internal_notes: payload.internal_notes,
              }
            : record
        )
      );
      setStatusMessage("Trust status updated.");
    } catch (caught) {
      const message =
        caught instanceof Error
          ? caught.message
          : "Failed to update trust status.";
      setError(message);
    } finally {
      setPendingId(null);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Trust Queue</h1>
        <p className="text-sm text-slate-600">
          Review quarantined candidates and override trust status.
        </p>
      </header>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {statusMessage ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {statusMessage}
        </div>
      ) : null}

      {records.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          No quarantined candidates.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {records.map((record) => (
            <section
              key={record.id}
              className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">
                    Trust #{record.id} - Resume {record.resume_document_id}
                  </div>
                  <div className="text-xs text-slate-500">
                    Score {record.score} - Status {record.status}
                  </div>
                </div>
                <div className="text-xs text-slate-400">
                  Updated {new Date(record.updated_at).toLocaleString()}
                </div>
              </div>

              <div className="mt-4 grid gap-3 text-xs text-slate-600 md:grid-cols-2">
                {record.reasons.map((reason, index) => (
                  <div
                    key={`${record.id}-reason-${index}`}
                    className="rounded-2xl border border-slate-100 bg-slate-50 p-3"
                  >
                    <div className="font-semibold text-slate-700">
                      {reason.code} - {reason.severity}
                    </div>
                    <p className="mt-1">{reason.message}</p>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex flex-col gap-3">
                <textarea
                  value={notes[record.id] ?? record.internal_notes ?? ""}
                  onChange={(event) =>
                    setNotes((current) => ({
                      ...current,
                      [record.id]: event.target.value,
                    }))
                  }
                  rows={2}
                  placeholder="Internal notes"
                  className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-xs"
                />
                <div className="flex flex-wrap gap-2">
                  {(["allowed", "soft_quarantine", "hard_quarantine"] as const).map(
                    (status) => (
                      <button
                        key={`${record.id}-${status}`}
                        type="button"
                        onClick={() => handleUpdate(record.id, status)}
                        disabled={pendingId === record.id}
                        className={`rounded-full px-4 py-2 text-xs font-semibold text-white ${
                          status === "allowed"
                            ? "bg-emerald-600"
                            : status === "soft_quarantine"
                            ? "bg-amber-600"
                            : "bg-rose-600"
                        } disabled:cursor-not-allowed disabled:opacity-70`}
                      >
                        Set {status.replace("_", " ")}
                      </button>
                    )
                  )}
                </div>
              </div>
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
