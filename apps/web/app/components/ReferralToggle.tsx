"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface ReferralResult {
  referred: boolean;
  interview_probability: number | null;
}

interface Props {
  matchId: number;
  referred: boolean;
  onReferralChange?: (data: ReferralResult) => void;
}

export default function ReferralToggle({ matchId, referred, onReferralChange }: Props) {
  const [isReferred, setIsReferred] = useState(referred);
  const [saving, setSaving] = useState(false);

  const handleToggle = async () => {
    const newValue = !isReferred;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/matches/${matchId}/referred`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ referred: newValue }),
      });
      if (res.ok) {
        const data = (await res.json()) as { id: number; referred: boolean; interview_probability: number | null };
        setIsReferred(data.referred);
        onReferralChange?.({ referred: data.referred, interview_probability: data.interview_probability });
      }
    } catch (err) {
      console.error("Error updating referral:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm hover:bg-gray-50">
      <input
        type="checkbox"
        checked={isReferred}
        onChange={handleToggle}
        disabled={saving}
        className="h-4 w-4 rounded border-gray-300 text-amber-500 focus:ring-amber-500"
      />
      <span className="text-sm font-medium text-gray-700">
        {saving ? "Updating..." : isReferred ? "Referred (8x boost)" : "I have a referral"}
      </span>
    </label>
  );
}
