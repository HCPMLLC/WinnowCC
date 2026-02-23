"use client";

import { Suspense, useEffect, useState, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "../lib/auth";
import { buildRedirectValue, withRedirectParam } from "../lib/redirects";
import { useProgress } from "../hooks/useProgress";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";

type ExperienceItem = {
  company?: string | null;
  title?: string | null;
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
  name?: string; // Computed from first_name + last_name, admin-editable only
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

type TrustStatusResponse = {
  trust_status: "allowed" | "soft_quarantine" | "hard_quarantine";
  score: number;
  user_message: string;
};

type TrustReviewResponse = {
  status: string;
};

type ResumeUploadResult = {
  resume_document_id: number;
  filename: string;
};

type ParseJobResult = {
  job_id: string;
  job_run_id: number;
  status: string;
};

type ParseJobStatus = {
  job_run_id: number;
  status: string;
  error_message?: string | null;
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

// Validates that a name is a full name (not an initial)
// Returns error message if invalid, null if valid
function validateFullName(value: string): string | null {
  if (!value || !value.trim()) {
    return null; // Empty is handled by required validation
  }
  const trimmed = value.trim();
  // Check for single letter or single letter followed by period (initials like "J." or "J")
  if (/^[A-Za-z]\.?$/.test(trimmed)) {
    return "Please enter your full name, not an initial.";
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

function ProfilePageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const recommendationsRef = useRef<HTMLDivElement>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [completeness, setCompleteness] =
    useState<ProfileCompletenessResponse | null>(null);
  const [trustStatus, setTrustStatus] = useState<TrustStatusResponse | null>(
    null
  );
  const [trustError, setTrustError] = useState<string | null>(null);
  const [trustRequestStatus, setTrustRequestStatus] = useState<string | null>(
    null
  );
  const [isRequestingReview, setIsRequestingReview] = useState(false);

  // Resume upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [resumeResult, setResumeResult] = useState<ResumeUploadResult | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<string | null>(null);
  const uploadProg = useProgress();
  const parseProg = useProgress();

  // Validation state for name fields
  const [firstNameError, setFirstNameError] = useState<string | null>(null);
  const [lastNameError, setLastNameError] = useState<string | null>(null);

  // Expanded state for sections
  const [expandedExperience, setExpandedExperience] = useState<number | null>(
    null
  );
  const [expandedEducation, setExpandedEducation] = useState<number | null>(
    null
  );

  useEffect(() => {
    const loadData = async () => {
      const me = await fetchAuthMe();
      if (!me) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/login", redirectValue));
        return;
      }
      if (!me.onboarding_complete) {
        const redirectValue = buildRedirectValue(pathname, searchParams);
        router.replace(withRedirectParam("/onboarding", redirectValue));
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
        const response = await fetch(`${API_BASE}/api/profile/completeness`, {
          credentials: "include",
        });
        if (response.ok) {
          const payload =
            (await response.json()) as ProfileCompletenessResponse;
          setCompleteness(payload);
        }
      } catch {
        // Non-critical, ignore
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
  }, [pathname, router, searchParams]);

  const updateBasics = (updates: Partial<Basics>) => {
    setProfile((current) => {
      if (!current) return current;
      const newBasics = { ...current.basics, ...updates };

      // Auto-compute name from first_name and last_name
      if ("first_name" in updates || "last_name" in updates) {
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

  const updateExperience = (index: number, updates: Partial<ExperienceItem>) => {
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

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      setTimeout(resolve, ms);
    });

  const handleResumeUpload = async () => {
    if (!selectedFile) {
      setResumeError("Please choose a PDF or DOCX file.");
      return;
    }
    uploadProg.start();
    setResumeError(null);
    setResumeResult(null);
    setParseStatus(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(`${API_BASE}/api/resume/upload`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        let message = "Upload failed. Please try again.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload?.detail) message = payload.detail;
        } catch {
          // Keep default message.
        }
        throw new Error(message);
      }
      const payload = (await response.json()) as ResumeUploadResult;
      setResumeResult(payload);
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Upload failed.";
      setResumeError(message);
    } finally {
      uploadProg.complete();
    }
  };

  const handleParse = async () => {
    if (!resumeResult) return;
    parseProg.start();
    setParseStatus(null);
    setResumeError(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/resume/${resumeResult.resume_document_id}/parse`,
        { method: "POST", credentials: "include" }
      );
      if (!response.ok) {
        let message = "Failed to start parsing.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload?.detail) message = payload.detail;
        } catch {
          // Keep default message.
        }
        throw new Error(message);
      }
      const payload = (await response.json()) as ParseJobResult;
      setParseStatus("Parse queued. Waiting for completion...");

      const maxTries = 20;
      for (let i = 0; i < maxTries; i += 1) {
        await sleep(1000);
        const statusResponse = await fetch(
          `${API_BASE}/api/resume/parse/${payload.job_run_id}`,
          { credentials: "include" }
        );
        if (!statusResponse.ok) {
          throw new Error("Failed to fetch parse status.");
        }
        const statusPayload = (await statusResponse.json()) as ParseJobStatus;
        if (statusPayload.status === "succeeded") {
          setParseStatus("Parse complete. Reloading profile...");
          // Reload the profile to reflect parsed data
          try {
            const profileResponse = await fetch(`${API_BASE}/api/profile`, {
              credentials: "include",
            });
            if (profileResponse.ok) {
              const profilePayload = (await profileResponse.json()) as ProfileResponse;
              setProfile(profilePayload.profile_json);
              setVersion(profilePayload.version);
            }
          } catch {
            // Non-critical
          }
          setParseStatus("Profile updated from resume.");
          return;
        }
        if (statusPayload.status === "failed") {
          throw new Error(
            statusPayload.error_message || "Parse failed. Please retry."
          );
        }
        setParseStatus(`Parsing... (${i + 1}/${maxTries})`);
      }
      setParseStatus("Parsing is taking longer than expected. Check back soon.");
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Failed to start parsing.";
      setResumeError(message);
    } finally {
      parseProg.complete();
    }
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
      setStatus("Profile saved.");

      // Refresh completeness score
      try {
        const completenessResponse = await fetch(
          `${API_BASE}/api/profile/completeness`,
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

  const scrollToRecommendations = () => {
    recommendationsRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  if (!profile) {
    return (
      <CandidateLayout>
        <div className="flex flex-col gap-6">
          <h1 className="text-3xl font-semibold">Profile</h1>
          <p className="text-sm text-slate-600">Loading profile...</p>
        </div>
      </CandidateLayout>
    );
  }

  return (
    <CandidateLayout>
      <div className="flex flex-col gap-8">
      <CollapsibleTip title="Build a Stronger Profile" defaultOpen={false}>
        <p>
          Higher completeness scores unlock better matches. Add work experience,
          skills, and education for the best results.
        </p>
      </CollapsibleTip>

      <header className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold">Profile</h1>
          <p className="text-sm text-slate-600">
            Version {version}. Edit your profile details and preferences.
          </p>
        </div>
        {completeness && (
          <CompletenesssBadge
            score={completeness.score}
            onClick={scrollToRecommendations}
          />
        )}
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

      {/* Resume Upload Section */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Resume</h2>
        <p className="mt-2 text-xs text-slate-500">
          Upload a PDF or DOCX (max 10MB) to auto-fill your profile.
        </p>
        <div className="mt-4 flex flex-col gap-4">
          <div className="flex items-center gap-4">
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={handleResumeUpload}
              disabled={!selectedFile || uploadProg.isActive}
              className="relative overflow-hidden rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-500"
            >
              {uploadProg.isActive && (
                <span
                  className="absolute inset-y-0 left-0 bg-slate-700 transition-all duration-200"
                  style={{ width: `${uploadProg.progress}%` }}
                />
              )}
              <span className="relative">
                {uploadProg.isActive
                  ? `Uploading... ${uploadProg.pct}%`
                  : "Upload"}
              </span>
            </button>
          </div>

          {resumeError && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {resumeError}
            </div>
          )}

          {resumeResult && (
            <div className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              <div>
                Uploaded: {resumeResult.filename}
              </div>
              <button
                type="button"
                onClick={handleParse}
                disabled={parseProg.isActive}
                className="relative w-fit overflow-hidden rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed"
              >
                {parseProg.isActive && (
                  <span
                    className="absolute inset-y-0 left-0 bg-emerald-600 transition-all duration-200"
                    style={{ width: `${parseProg.progress}%` }}
                  />
                )}
                <span className="relative">
                  {parseProg.isActive
                    ? `Building profile... ${parseProg.pct}%`
                    : "Build my profile"}
                </span>
              </button>
              {parseStatus && (
                <div className="text-sm text-emerald-900">{parseStatus}</div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Basics Section */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Basic Information</h2>
        <p className="mt-2 text-xs text-slate-500">
          Please enter your full name as it appears on official documents. Initials are not accepted.
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
              required
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
              required
            />
            {lastNameError && (
              <p className="text-xs text-red-600">{lastNameError}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-slate-700">
              Full Name
              <span className="ml-2 text-xs font-normal text-slate-400">
                (auto-generated)
              </span>
            </label>
            <input
              type="text"
              value={profile.basics.name ?? ""}
              readOnly
              disabled
              className="rounded-xl border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-500 cursor-not-allowed"
              placeholder="Auto-generated from First and Last Name"
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
              onBlur={(e) => {
                const val = e.target.value.trim();
                if (!val) return;
                const parts = val.split(",");
                if (parts.length >= 2) {
                  const city = parts[0]
                    .trim()
                    .toLowerCase()
                    .replace(/\b\w/g, (c) => c.toUpperCase());
                  const st = parts[1].trim().toUpperCase().slice(0, 2);
                  const rest = parts.slice(2).map((p) => p.trim());
                  updateBasics({
                    location: [city, st, ...rest].join(", "),
                  });
                } else {
                  updateBasics({
                    location: val
                      .toLowerCase()
                      .replace(/\b\w/g, (c) => c.toUpperCase()),
                  });
                }
              }}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="New York, NY"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Total Years of Experience
            <input
              type="number"
              min={1}
              max={51}
              step={1}
              inputMode="numeric"
              pattern="[0-9]*"
              value={profile.basics.total_years_experience ?? ""}
              onChange={(e) => {
                const raw = e.target.value.replace(/[^0-9]/g, "");
                if (!raw) {
                  updateBasics({ total_years_experience: null });
                  return;
                }
                const num = Math.min(51, Math.max(1, parseInt(raw, 10)));
                updateBasics({ total_years_experience: num });
              }}
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
            No experience entries yet. Click &quot;Add Experience&quot; to add your work history.
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
            No education entries yet. Click &quot;Add Education&quot; to add your educational background.
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
          <div className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Target titles
            <TagInput
              value={profile.preferences.target_titles}
              onChange={(tags) => updatePreferences({ target_titles: tags })}
              placeholder="Type a title and press Enter"
            />
          </div>
          <div className="flex flex-col gap-2 text-sm font-medium text-slate-700">
            Locations
            <TagInput
              value={profile.preferences.locations}
              onChange={(tags) => updatePreferences({ locations: tags })}
              placeholder="Type a location and press Enter"
            />
          </div>
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
      </div>
    </CandidateLayout>
  );
}

export default function ProfilePage() {
  return (
    <Suspense>
      <ProfilePageContent />
    </Suspense>
  );
}
