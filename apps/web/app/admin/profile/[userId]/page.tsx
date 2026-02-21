"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";

type ExperienceItem = {
  company?: string | null;
  title?: string | null;
  job_location?: string | null;  // City, ST format (e.g., "San Diego, CA")
  start_date?: string | null;
  end_date?: string | null;
  bullets?: string[];
  duties?: string[];
  skills_used?: string[];
  technologies_used?: string[];
  quantified_accomplishments?: string[];
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

type Basics = {
  first_name?: string;
  last_name?: string;
  name?: string; // Admin can edit this directly
  email?: string;
  phone?: string;
  location?: string;
  total_years_experience?: number | null;
  work_authorization?: string | null;
};

type CandidateProfile = {
  basics: Basics;
  experience: ExperienceItem[];
  education: EducationItem[];
  skills: string[];
  preferences: Preferences;
};

type ProfileResponse = {
  version: number;
  profile_json: CandidateProfile;
};

type ProfileDeficiency = {
  field: string;
  message: string;
  weight: number;
};

type ProfileCompletenessResponse = {
  score: number;
  deficiencies: ProfileDeficiency[];
  recommendations: string[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const WORK_AUTHORIZATION_OPTIONS = [
  "US Citizen",
  "Green Card",
  "H1B",
  "H1B Transfer",
  "L1",
  "OPT",
  "OPT STEM",
  "TN Visa",
  "E-2",
  "Other Work Visa",
  "Requires Sponsorship",
];

const parseCommaList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

// Validates that a name is a full name (not an initial)
// Returns error message if invalid, null if valid
function validateFullName(value: string): string | null {
  if (!value || !value.trim()) {
    return null; // Empty is handled by required validation
  }
  const trimmed = value.trim();
  // Check for single letter or single letter followed by period (initials like "J." or "J")
  if (/^[A-Za-z]\.?$/.test(trimmed)) {
    return "Please enter a full name, not an initial.";
  }
  // Check for minimum length (at least 2 characters)
  if (trimmed.length < 2) {
    return "Name must be at least 2 characters.";
  }
  return null;
}

function CompletenesssBadge({
  score,
  onClick,
}: {
  score: number;
  onClick: () => void;
}) {
  const color =
    score >= 80
      ? "text-emerald-600 border-emerald-200 bg-emerald-50"
      : score >= 50
        ? "text-amber-600 border-amber-200 bg-amber-50"
        : "text-red-600 border-red-200 bg-red-50";

  const strokeColor =
    score >= 80 ? "#059669" : score >= 50 ? "#d97706" : "#dc2626";

  const circumference = 2 * Math.PI * 18;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors hover:opacity-80 ${color}`}
    >
      <svg width="40" height="40" className="-rotate-90">
        <circle
          cx="20"
          cy="20"
          r="18"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          opacity="0.2"
        />
        <circle
          cx="20"
          cy="20"
          r="18"
          fill="none"
          stroke={strokeColor}
          strokeWidth="3"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
        />
      </svg>
      <span>{score}% Complete</span>
    </button>
  );
}

function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [inputValue, setInputValue] = useState("");

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const newTag = inputValue.trim();
      if (newTag && !value.includes(newTag)) {
        onChange([...value, newTag]);
      }
      setInputValue("");
    } else if (e.key === "Backspace" && !inputValue && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const removeTag = (tagToRemove: string) => {
    onChange(value.filter((tag) => tag !== tagToRemove));
  };

  return (
    <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 p-2">
      {value.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tag)}
            className="ml-1 text-slate-400 hover:text-slate-600"
          >
            &times;
          </button>
        </span>
      ))}
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={value.length === 0 ? placeholder : "Add more..."}
        className="min-w-[120px] flex-1 border-none bg-transparent px-1 py-1 text-sm outline-none"
      />
    </div>
  );
}

function BulletListEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (bullets: string[]) => void;
  placeholder?: string;
}) {
  const addBullet = () => {
    onChange([...value, ""]);
  };

  const updateBullet = (index: number, newValue: string) => {
    const updated = [...value];
    updated[index] = newValue;
    onChange(updated);
  };

  const removeBullet = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-col gap-2">
      {value.map((bullet, index) => (
        <div key={index} className="flex items-start gap-2">
          <span className="mt-2.5 text-slate-400">&bull;</span>
          <input
            type="text"
            value={bullet}
            onChange={(e) => updateBullet(index, e.target.value)}
            placeholder={placeholder}
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => removeBullet(index)}
            className="mt-1.5 text-slate-400 hover:text-red-500"
          >
            &times;
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addBullet}
        className="w-fit text-xs text-slate-500 hover:text-slate-700"
      >
        + Add item
      </button>
    </div>
  );
}

export default function AdminProfileEditorPage() {
  const router = useRouter();
  const params = useParams();
  const userId = params.userId as string;
  const recommendationsRef = useRef<HTMLDivElement>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [version, setVersion] = useState(0);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [completeness, setCompleteness] =
    useState<ProfileCompletenessResponse | null>(null);

  // Validation state for name fields
  const [firstNameError, setFirstNameError] = useState<string | null>(null);
  const [lastNameError, setLastNameError] = useState<string | null>(null);

  const [expandedExperience, setExpandedExperience] = useState<number | null>(
    null
  );
  const [expandedEducation, setExpandedEducation] = useState<number | null>(
    null
  );

  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/admin/profile/${userId}`,
          {
            credentials: "include",
          }
        );
        if (response.status === 401) {
          router.push("/login");
          return;
        }
        if (response.status === 403) {
          setError("Admin access required.");
          return;
        }
        if (response.status === 404) {
          setError("User not found.");
          return;
        }
        if (!response.ok) {
          throw new Error("Failed to load profile.");
        }
        const payload = (await response.json()) as ProfileResponse;
        setProfile(payload.profile_json);
        setVersion(payload.version);
        setUserEmail(payload.profile_json.basics?.email || null);
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "Failed to load profile.";
        setError(message);
      }

      try {
        const response = await fetch(
          `${API_BASE}/api/admin/profile/${userId}/completeness`,
          {
            credentials: "include",
          }
        );
        if (response.ok) {
          const payload =
            (await response.json()) as ProfileCompletenessResponse;
          setCompleteness(payload);
        }
      } catch {
        // Non-critical
      }
    };

    void loadData();
  }, [userId, router]);

  const updateBasics = (updates: Partial<Basics>) => {
    setProfile((current) => {
      if (!current) return current;
      const newBasics = { ...current.basics, ...updates };

      // Auto-compute name from first_name and last_name if not directly updating name
      if (("first_name" in updates || "last_name" in updates) && !("name" in updates)) {
        const firstName = newBasics.first_name?.trim() || "";
        const lastName = newBasics.last_name?.trim() || "";
        newBasics.name = [firstName, lastName].filter(Boolean).join(" ");
      }

      return {
        ...current,
        basics: newBasics,
      };
    });

    // Validate first_name if it was updated
    if ("first_name" in updates) {
      const error = validateFullName(updates.first_name || "");
      setFirstNameError(error);
    }

    // Validate last_name if it was updated
    if ("last_name" in updates) {
      const error = validateFullName(updates.last_name || "");
      setLastNameError(error);
    }
  };

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

  const updateExperience = (
    index: number,
    updates: Partial<ExperienceItem>
  ) => {
    setProfile((current) => {
      if (!current) return current;
      const updated = [...current.experience];
      updated[index] = { ...updated[index], ...updates };
      return { ...current, experience: updated };
    });
  };

  const addExperience = () => {
    setProfile((current) => {
      if (!current) return current;
      return {
        ...current,
        experience: [
          ...current.experience,
          {
            company: "",
            title: "",
            start_date: "",
            end_date: "",
            bullets: [],
            duties: [],
            skills_used: [],
            technologies_used: [],
            quantified_accomplishments: [],
          },
        ],
      };
    });
    setExpandedExperience(profile?.experience.length ?? 0);
  };

  const removeExperience = (index: number) => {
    setProfile((current) => {
      if (!current) return current;
      return {
        ...current,
        experience: current.experience.filter((_, i) => i !== index),
      };
    });
    setExpandedExperience(null);
  };

  const updateEducation = (index: number, updates: Partial<EducationItem>) => {
    setProfile((current) => {
      if (!current) return current;
      const updated = [...current.education];
      updated[index] = { ...updated[index], ...updates };
      return { ...current, education: updated };
    });
  };

  const addEducation = () => {
    setProfile((current) => {
      if (!current) return current;
      return {
        ...current,
        education: [
          ...current.education,
          {
            school: "",
            degree: "",
            field: "",
            start_date: "",
            end_date: "",
          },
        ],
      };
    });
    setExpandedEducation(profile?.education.length ?? 0);
  };

  const removeEducation = (index: number) => {
    setProfile((current) => {
      if (!current) return current;
      return {
        ...current,
        education: current.education.filter((_, i) => i !== index),
      };
    });
    setExpandedEducation(null);
  };

  const handleSave = async () => {
    if (!profile) {
      return;
    }

    // Validate required name fields
    const firstNameValidation = validateFullName(profile.basics.first_name || "");
    const lastNameValidation = validateFullName(profile.basics.last_name || "");

    // Check for empty required fields
    if (!profile.basics.first_name?.trim()) {
      setFirstNameError("First name is required.");
      setError("Please fill in all required fields.");
      return;
    }
    if (!profile.basics.last_name?.trim()) {
      setLastNameError("Last name is required.");
      setError("Please fill in all required fields.");
      return;
    }

    // Check for validation errors
    if (firstNameValidation) {
      setFirstNameError(firstNameValidation);
      setError("Please correct the errors before saving.");
      return;
    }
    if (lastNameValidation) {
      setLastNameError(lastNameValidation);
      setError("Please correct the errors before saving.");
      return;
    }

    setIsSaving(true);
    setStatus(null);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/admin/profile/${userId}`, {
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
      setStatus("Profile saved.");

      // Refresh completeness score
      try {
        const completenessResponse = await fetch(
          `${API_BASE}/api/admin/profile/${userId}/completeness`,
          {
            credentials: "include",
          }
        );
        if (completenessResponse.ok) {
          const completenessPayload =
            (await completenessResponse.json()) as ProfileCompletenessResponse;
          setCompleteness(completenessPayload);
        }
      } catch {
        // Non-critical
      }
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to save profile.";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const scrollToRecommendations = () => {
    recommendationsRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  if (!profile) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
        <Link
          href="/admin/profile"
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          &larr; Back to Users
        </Link>
        <h1 className="text-3xl font-semibold">Edit Profile</h1>
        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <p className="text-sm text-slate-600">Loading profile...</p>
        )}
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-16">
      <Link
        href="/admin/profile"
        className="text-sm text-slate-500 hover:text-slate-700"
      >
        &larr; Back to Users
      </Link>

      <header className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold">Edit Profile</h1>
          <p className="text-sm text-slate-600">
            User ID: {userId}
            {userEmail ? ` (${userEmail})` : ""} | Version {version}
          </p>
        </div>
        {completeness && (
          <CompletenesssBadge
            score={completeness.score}
            onClick={scrollToRecommendations}
          />
        )}
      </header>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {status ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {status}
        </div>
      ) : null}

      {/* Basics Section */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Basic Information</h2>
        <p className="mt-2 text-xs text-slate-500">
          Full names required. Initials are not accepted. As an admin, you can also directly edit the Full Name field.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-slate-700">
              First Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={profile.basics.first_name ?? ""}
              onChange={(e) => updateBasics({ first_name: e.target.value })}
              className={`rounded-xl border px-3 py-2 text-sm ${
                firstNameError
                  ? "border-red-300 bg-red-50"
                  : "border-slate-200"
              }`}
              placeholder="John"
            />
            {firstNameError && (
              <p className="text-xs text-red-600">{firstNameError}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-slate-700">
              Last Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={profile.basics.last_name ?? ""}
              onChange={(e) => updateBasics({ last_name: e.target.value })}
              className={`rounded-xl border px-3 py-2 text-sm ${
                lastNameError
                  ? "border-red-300 bg-red-50"
                  : "border-slate-200"
              }`}
              placeholder="Doe"
            />
            {lastNameError && (
              <p className="text-xs text-red-600">{lastNameError}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-slate-700">
              Full Name
              <span className="ml-2 text-xs font-normal text-amber-600">
                (admin editable)
              </span>
            </label>
            <input
              type="text"
              value={profile.basics.name ?? ""}
              onChange={(e) => updateBasics({ name: e.target.value })}
              className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm"
              placeholder="John Doe"
            />
          </div>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              value={profile.basics.email ?? ""}
              onChange={(e) => updateBasics({ email: e.target.value })}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="john@example.com"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Phone
            <input
              type="tel"
              value={profile.basics.phone ?? ""}
              onChange={(e) => updateBasics({ phone: e.target.value })}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="+1 555-123-4567"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Location
            <input
              type="text"
              value={profile.basics.location ?? ""}
              onChange={(e) => updateBasics({ location: e.target.value })}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="New York, NY"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Total Years of Experience
            <input
              type="number"
              min="0"
              value={profile.basics.total_years_experience ?? ""}
              onChange={(e) =>
                updateBasics({
                  total_years_experience: e.target.value
                    ? Number(e.target.value)
                    : null,
                })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="5"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Work Authorization
            <select
              value={profile.basics.work_authorization ?? ""}
              onChange={(e) =>
                updateBasics({
                  work_authorization: e.target.value || null,
                })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Select...</option>
              {WORK_AUTHORIZATION_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {/* Experience Section */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Experience</h2>
          <button
            type="button"
            onClick={addExperience}
            className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200"
          >
            + Add Experience
          </button>
        </div>
        {profile.experience.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600">
            No experience entries yet.
          </p>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            {profile.experience.map((item, index) => (
              <div
                key={`exp-${index}`}
                className="rounded-xl border border-slate-100 bg-slate-50 p-4"
              >
                <div
                  className="flex cursor-pointer items-center justify-between"
                  onClick={() =>
                    setExpandedExperience(
                      expandedExperience === index ? null : index
                    )
                  }
                >
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {item.title || "Role"}
                      {item.company ? ` · ${item.company}` : ""}
                      {item.job_location ? ` · ${item.job_location}` : ""}
                    </div>
                    {item.start_date || item.end_date ? (
                      <div className="text-xs text-slate-500">
                        {[item.start_date, item.end_date]
                          .filter(Boolean)
                          .join(" - ")}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeExperience(index);
                      }}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
                    <span className="text-slate-400">
                      {expandedExperience === index ? "▼" : "▶"}
                    </span>
                  </div>
                </div>

                {expandedExperience === index && (
                  <div className="mt-4 flex flex-col gap-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        Company
                        <input
                          type="text"
                          value={item.company ?? ""}
                          onChange={(e) =>
                            updateExperience(index, { company: e.target.value })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                          placeholder="Company Name"
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        Title
                        <input
                          type="text"
                          value={item.title ?? ""}
                          onChange={(e) =>
                            updateExperience(index, { title: e.target.value })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                          placeholder="Software Engineer"
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        Job Location
                        <input
                          type="text"
                          value={item.job_location ?? ""}
                          onChange={(e) =>
                            updateExperience(index, { job_location: e.target.value })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                          placeholder="City, ST (e.g., San Diego, CA)"
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        Start Date
                        <input
                          type="month"
                          value={item.start_date ?? ""}
                          onChange={(e) =>
                            updateExperience(index, {
                              start_date: e.target.value,
                            })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        End Date
                        <input
                          type="month"
                          value={item.end_date ?? ""}
                          onChange={(e) =>
                            updateExperience(index, {
                              end_date: e.target.value,
                            })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                          placeholder="Present"
                        />
                      </label>
                    </div>

                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-slate-700">
                        Duties
                      </span>
                      <BulletListEditor
                        value={item.duties ?? []}
                        onChange={(duties) =>
                          updateExperience(index, { duties })
                        }
                        placeholder="e.g., Managed team of 5 engineers"
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-slate-700">
                        Quantified Accomplishments
                      </span>
                      <BulletListEditor
                        value={item.quantified_accomplishments ?? []}
                        onChange={(quantified_accomplishments) =>
                          updateExperience(index, { quantified_accomplishments })
                        }
                        placeholder="e.g., Increased revenue by 25%"
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-slate-700">
                        Skills Used
                      </span>
                      <TagInput
                        value={item.skills_used ?? []}
                        onChange={(skills_used) =>
                          updateExperience(index, { skills_used })
                        }
                        placeholder="e.g., Leadership, Project Management"
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-slate-700">
                        Technologies Used
                      </span>
                      <TagInput
                        value={item.technologies_used ?? []}
                        onChange={(technologies_used) =>
                          updateExperience(index, { technologies_used })
                        }
                        placeholder="e.g., React, Python, AWS"
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-slate-700">
                        Original Bullets
                      </span>
                      <BulletListEditor
                        value={item.bullets ?? []}
                        onChange={(bullets) =>
                          updateExperience(index, { bullets })
                        }
                        placeholder="Original resume bullet point"
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Education Section */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Education</h2>
          <button
            type="button"
            onClick={addEducation}
            className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200"
          >
            + Add Education
          </button>
        </div>
        {profile.education.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600">
            No education entries yet.
          </p>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            {profile.education.map((item, index) => (
              <div
                key={`edu-${index}`}
                className="rounded-xl border border-slate-100 bg-slate-50 p-4"
              >
                <div
                  className="flex cursor-pointer items-center justify-between"
                  onClick={() =>
                    setExpandedEducation(
                      expandedEducation === index ? null : index
                    )
                  }
                >
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {item.degree || "Degree"}
                      {item.field ? ` in ${item.field}` : ""}
                    </div>
                    <div className="text-xs text-slate-500">
                      {item.school || "School"}
                      {item.start_date || item.end_date
                        ? ` · ${[item.start_date, item.end_date].filter(Boolean).join(" - ")}`
                        : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeEducation(index);
                      }}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
                    <span className="text-slate-400">
                      {expandedEducation === index ? "▼" : "▶"}
                    </span>
                  </div>
                </div>

                {expandedEducation === index && (
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                      School
                      <input
                        type="text"
                        value={item.school ?? ""}
                        onChange={(e) =>
                          updateEducation(index, { school: e.target.value })
                        }
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        placeholder="University Name"
                      />
                    </label>
                    <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                      Degree
                      <input
                        type="text"
                        value={item.degree ?? ""}
                        onChange={(e) =>
                          updateEducation(index, { degree: e.target.value })
                        }
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        placeholder="Bachelor of Science"
                      />
                    </label>
                    <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                      Field of Study
                      <input
                        type="text"
                        value={item.field ?? ""}
                        onChange={(e) =>
                          updateEducation(index, { field: e.target.value })
                        }
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        placeholder="Computer Science"
                      />
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        Start Date
                        <input
                          type="month"
                          value={item.start_date ?? ""}
                          onChange={(e) =>
                            updateEducation(index, {
                              start_date: e.target.value,
                            })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                        End Date
                        <input
                          type="month"
                          value={item.end_date ?? ""}
                          onChange={(e) =>
                            updateEducation(index, {
                              end_date: e.target.value,
                            })
                          }
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        />
                      </label>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Skills Section */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Skills</h2>
        <div className="mt-4">
          <TagInput
            value={profile.skills}
            onChange={(skills) =>
              setProfile((current) =>
                current ? { ...current, skills } : current
              )
            }
            placeholder="Type a skill and press Enter"
          />
        </div>
      </section>

      {/* Preferences Section */}
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
                updatePreferences({
                  locations: parseCommaList(event.target.value),
                })
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Austin, San Diego, Detroit, Alexandria"
              title="Enter city names separated by commas. Use full city names (e.g. San Francisco, not SF). Leave blank to match all locations."
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
            <div className="flex flex-wrap gap-2">
              {["Full-time", "Part-time", "Contract", "Internship"].map((jt) => {
                const selected = (profile.preferences.job_type ?? "")
                  .split(",")
                  .map((s: string) => s.trim())
                  .filter(Boolean);
                const isSelected = selected.includes(jt);
                return (
                  <button
                    key={jt}
                    type="button"
                    onClick={() => {
                      const next = isSelected
                        ? selected.filter((s: string) => s !== jt)
                        : [...selected, jt];
                      updatePreferences({
                        job_type: next.length > 0 ? next.join(", ") : null,
                      });
                    }}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                      isSelected
                        ? "border-slate-900 bg-slate-900 text-white"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-400"
                    }`}
                  >
                    {jt}
                  </button>
                );
              })}
            </div>
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
      </section>

      {/* Recommendations Panel */}
      {completeness &&
        (completeness.deficiencies.length > 0 ||
          completeness.recommendations.length > 0) && (
          <section
            ref={recommendationsRef}
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <h2 className="text-lg font-semibold">Profile Recommendations</h2>

            {completeness.deficiencies.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-slate-700">
                  Missing Information
                </h3>
                <ul className="mt-2 flex flex-col gap-2">
                  {completeness.deficiencies.map((d, i) => (
                    <li
                      key={i}
                      className={`flex items-center gap-2 text-sm ${
                        d.weight >= 10
                          ? "text-red-600"
                          : d.weight >= 5
                            ? "text-amber-600"
                            : "text-slate-600"
                      }`}
                    >
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${
                          d.weight >= 10
                            ? "bg-red-500"
                            : d.weight >= 5
                              ? "bg-amber-500"
                              : "bg-slate-400"
                        }`}
                      />
                      {d.message}
                      <span className="text-xs text-slate-400">
                        ({d.field})
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {completeness.recommendations.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-slate-700">
                  Suggestions
                </h3>
                <ul className="mt-2 flex flex-col gap-2">
                  {completeness.recommendations.map((rec, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-2 text-sm text-slate-600"
                    >
                      <span className="text-emerald-500">→</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-500"
        >
          {isSaving ? "Saving..." : "Save Profile"}
        </button>
      </div>
    </main>
  );
}
