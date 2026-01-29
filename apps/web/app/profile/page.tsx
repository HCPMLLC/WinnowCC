"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";

type ExperienceItem = {
  company?: string | null;
  title?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  bullets?: string[];
};

type EducationItem = {
  school?: string | null;
  degree?: string | null;
  field?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

type Preferences = {
  target_titles: string[];
  locations: string[];
  remote_ok: boolean | null;
  job_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
};

type CandidateProfile = {
  basics: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
  };
  experience: ExperienceItem[];
  education: EducationItem[];
  skills: string[];
  preferences: Preferences;
};

type ProfileResponse = {
  version: number;
  profile_json: CandidateProfile;
};

type TrustStatusResponse = {
  trust_status: "allowed" | "soft_quarantine" | "hard_quarantine";
  score: number;
  user_message: string;
};

type TrustReviewResponse = {
  status: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const parseCommaList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [trustStatus, setTrustStatus] = useState<TrustStatusResponse | null>(
    null
  );
  const [trustError, setTrustError] = useState<string | null>(null);
  const [trustRequestStatus, setTrustRequestStatus] = useState<string | null>(
    null
  );
  const [isRequestingReview, setIsRequestingReview] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        router.replace("/login");
        return;
      }
      if (!me.onboarding_complete) {
        router.replace("/onboarding");
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/api/profile`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load profile.");
        }
        const payload = (await response.json()) as ProfileResponse;
        setProfile(payload.profile_json);
        setVersion(payload.version);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load profile.";
        setError(message);
      }

      try {
        const response = await fetch(`${API_BASE}/api/trust/me`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to load trust status.");
        }
        const payload = (await response.json()) as TrustStatusResponse;
        setTrustStatus(payload);
      } catch (caught) {
        const message =
          caught instanceof Error
            ? caught.message
            : "Failed to load trust status.";
        setTrustError(message);
      }
    };

    void loadData();
  }, [router]);

  const updatePreferences = (updates: Partial<Preferences>) => {
    setProfile((current) =>
      current
        ? {
            ...current,
            preferences: { ...current.preferences, ...updates },
          }
        : current
    );
  };

  const handleSave = async () => {
    if (!profile) {
      return;
    }
    setIsSaving(true);
    setStatus(null);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ profile_json: profile }),
      });
      if (!response.ok) {
        let message = "Failed to save profile.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload?.detail) {
            message = payload.detail;
          }
        } catch {
          // Keep default message.
        }
        throw new Error(message);
      }
      const payload = (await response.json()) as ProfileResponse;
      setVersion(payload.version);
      setProfile(payload.profile_json);
      setStatus("Preferences saved.");
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to save profile.";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRequestReview = async () => {
    setIsRequestingReview(true);
    setTrustRequestStatus(null);
    setTrustError(null);
    try {
      const response = await fetch(`${API_BASE}/api/trust/me/request-review`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to request review.");
      }
      const payload = (await response.json()) as TrustReviewResponse;
      setTrustRequestStatus(
        payload.status === "received"
          ? "Review requested. We'll follow up with next steps."
          : "Review request sent."
      );
    } catch (caught) {
      const message =
        caught instanceof Error
          ? caught.message
          : "Failed to request review.";
      setTrustError(message);
    } finally {
      setIsRequestingReview(false);
    }
  };

  if (!profile) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
        <h1 className="text-3xl font-semibold">Profile</h1>
        <p className="text-sm text-slate-600">Loading profile...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Profile</h1>
        <p className="text-sm text-slate-600">
          Version {version}. Review extracted details and update your preferences.
        </p>
      </header>

      {trustStatus && trustStatus.trust_status !== "allowed" ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="font-semibold">
            Your account requires verification before job matching.
          </div>
          <p className="mt-2 text-xs text-amber-800">
            Request a review to continue the verification process.
          </p>
          <button
            type="button"
            onClick={handleRequestReview}
            disabled={isRequestingReview}
            className="mt-3 w-fit rounded-full bg-amber-900 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-amber-700"
          >
            {isRequestingReview ? "Requesting..." : "Request review"}
          </button>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {trustError ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {trustError}
        </div>
      ) : null}

      {status ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {status}
        </div>
      ) : null}

      {trustRequestStatus ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {trustRequestStatus}
        </div>
      ) : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Experience</h2>
        {profile.experience.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">
            No experience parsed yet.
          </p>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            {profile.experience.map((item, index) => (
              <div key={`${item.company ?? "role"}-${index}`}>
                <div className="text-sm font-semibold text-slate-900">
                  {item.title || "Role"}
                  {item.company ? ` · ${item.company}` : ""}
                </div>
                {item.start_date || item.end_date ? (
                  <div className="text-xs text-slate-500">
                    {[item.start_date, item.end_date]
                      .filter(Boolean)
                      .join(" - ")}
                  </div>
                ) : null}
                {item.bullets && item.bullets.length > 0 ? (
                  <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
                    {item.bullets.map((bullet, bulletIndex) => (
                      <li key={`${index}-${bulletIndex}`}>{bullet}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Skills</h2>
        {profile.skills.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">No skills parsed yet.</p>
        ) : (
          <div className="mt-4 flex flex-wrap gap-2">
            {profile.skills.map((skill) => (
              <span
                key={skill}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700"
              >
                {skill}
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Preferences</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Target titles
            <input
              type="text"
              value={profile.preferences.target_titles.join(", ")}
              onChange={(event) =>
                updatePreferences({
                  target_titles: parseCommaList(event.target.value),
                })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Product Manager, Data Analyst"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Locations
            <input
              type="text"
              value={profile.preferences.locations.join(", ")}
              onChange={(event) =>
                updatePreferences({ locations: parseCommaList(event.target.value) })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="New York, Remote"
            />
          </label>
          <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={profile.preferences.remote_ok ?? false}
              onChange={(event) =>
                updatePreferences({ remote_ok: event.target.checked })
              }
              className="h-4 w-4 rounded border-slate-300"
            />
            Remote OK
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Job type
            <input
              type="text"
              value={profile.preferences.job_type ?? ""}
              onChange={(event) =>
                updatePreferences({ job_type: event.target.value || null })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Full-time"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Salary minimum
            <input
              type="number"
              value={profile.preferences.salary_min ?? ""}
              onChange={(event) =>
                updatePreferences({
                  salary_min: event.target.value
                    ? Number(event.target.value)
                    : null,
                })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="80000"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Salary maximum
            <input
              type="number"
              value={profile.preferences.salary_max ?? ""}
              onChange={(event) =>
                updatePreferences({
                  salary_max: event.target.value
                    ? Number(event.target.value)
                    : null,
                })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="120000"
            />
          </label>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="mt-6 w-fit rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-500"
        >
          {isSaving ? "Saving..." : "Save preferences"}
        </button>
      </section>
    </main>
  );
}
