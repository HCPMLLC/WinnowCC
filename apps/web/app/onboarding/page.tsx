"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const parseCommaList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export default function OnboardingPage() {
  const router = useRouter();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [locationCity, setLocationCity] = useState("");
  const [state, setState] = useState("");
  const [country, setCountry] = useState("");
  const [workAuthorization, setWorkAuthorization] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [desiredJobTypes, setDesiredJobTypes] = useState("");
  const [desiredLocations, setDesiredLocations] = useState("");
  const [desiredSalaryMin, setDesiredSalaryMin] = useState("");
  const [desiredSalaryMax, setDesiredSalaryMax] = useState("");
  const [remotePreference, setRemotePreference] = useState("no_preference");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE}/api/onboarding/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          first_name: firstName || null,
          last_name: lastName || null,
          phone: phone || null,
          location_city: locationCity || null,
          state: state || null,
          country: country || null,
          work_authorization: workAuthorization || null,
          years_experience: yearsExperience ? Number(yearsExperience) : null,
          desired_job_types: parseCommaList(desiredJobTypes),
          desired_locations: parseCommaList(desiredLocations),
          desired_salary_min: desiredSalaryMin ? Number(desiredSalaryMin) : null,
          desired_salary_max: desiredSalaryMax ? Number(desiredSalaryMax) : null,
          remote_preference: remotePreference || null,
        }),
      });

      if (!response.ok) {
        let message = "Failed to save onboarding details.";
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

      router.push("/upload");
    } catch (caught) {
      const message =
        caught instanceof Error
          ? caught.message
          : "Failed to save onboarding details.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">Onboarding</h1>
        <p className="text-sm text-slate-600">
          Tell us a bit about your preferences so we can personalize matching.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-5 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            First name
            <input
              type="text"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Last name
            <input
              type="text"
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Phone
            <input
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            City
            <input
              type="text"
              value={locationCity}
              onChange={(event) => setLocationCity(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            State
            <input
              type="text"
              value={state}
              onChange={(event) => setState(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Country
            <input
              type="text"
              value={country}
              onChange={(event) => setCountry(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Work authorization
            <input
              type="text"
              value={workAuthorization}
              onChange={(event) => setWorkAuthorization(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="US Citizen, H1B, etc."
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Years of experience
            <input
              type="number"
              min={0}
              value={yearsExperience}
              onChange={(event) => setYearsExperience(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Desired job types (comma-separated)
            <input
              type="text"
              value={desiredJobTypes}
              onChange={(event) => setDesiredJobTypes(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Full-time, Contract"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Desired locations (comma-separated)
            <input
              type="text"
              value={desiredLocations}
              onChange={(event) => setDesiredLocations(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="New York, Remote"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Desired salary minimum
            <input
              type="number"
              min={0}
              value={desiredSalaryMin}
              onChange={(event) => setDesiredSalaryMin(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="80000"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Desired salary maximum
            <input
              type="number"
              min={0}
              value={desiredSalaryMax}
              onChange={(event) => setDesiredSalaryMax(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="120000"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Remote preference
            <select
              value={remotePreference}
              onChange={(event) => setRemotePreference(event.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="no_preference">No preference</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </label>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-fit rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-500"
        >
          {isSubmitting ? "Saving..." : "Continue"}
        </button>
      </form>
    </main>
  );
}
