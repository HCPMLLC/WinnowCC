"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const STATUSES = [
  { value: "", label: "— No status —", color: "bg-gray-100 text-gray-600" },
  { value: "saved", label: "Saved", color: "bg-blue-100 text-blue-800" },
  { value: "applied", label: "Applied", color: "bg-yellow-100 text-yellow-800" },
  { value: "interviewing", label: "Interviewing", color: "bg-purple-100 text-purple-800" },
  { value: "rejected", label: "Rejected", color: "bg-red-100 text-red-800" },
  { value: "offer", label: "Offer", color: "bg-green-100 text-green-800" },
  { value: "dismissed", label: "Dismissed", color: "bg-gray-200 text-gray-500" },
];

interface Props {
  matchId: number;
  currentStatus: string | null;
  onStatusChange?: (newStatus: string) => void;
}

export default function ApplicationStatusSelect({ matchId, currentStatus, onStatusChange }: Props) {
  const [status, setStatus] = useState(currentStatus || "");
  const [saving, setSaving] = useState(false);

  const handleChange = async (newStatus: string) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/matches/${matchId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus || null }),
      });
      if (res.ok) {
        setStatus(newStatus);
        onStatusChange?.(newStatus);
      } else {
        console.error("Failed to update status");
      }
    } catch (err) {
      console.error("Error updating status:", err);
    } finally {
      setSaving(false);
    }
  };

  const current = STATUSES.find((s) => s.value === status) || STATUSES[0];

  return (
    <div className="flex items-center gap-2">
      <select
        value={status}
        onChange={(e) => handleChange(e.target.value)}
        disabled={saving}
        className={`text-sm font-medium rounded-md px-3 py-1.5 border border-gray-300
                     focus:outline-none focus:ring-2 focus:ring-green-500 ${current.color}
                     ${saving ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
      >
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      {saving && <span className="text-xs text-gray-400">Saving...</span>}
    </div>
  );
}
