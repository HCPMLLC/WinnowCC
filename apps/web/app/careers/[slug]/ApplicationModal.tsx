"use client";

import { useState, useEffect, useRef } from "react";
import {
  X,
  Upload,
  CheckCircle2,
  Loader2,
  Briefcase,
  MapPin,
  ChevronRight,
  AlertCircle,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

type Step = "email" | "resume" | "form" | "done";

interface FormData {
  first_name: string;
  last_name: string;
  current_title: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  phone: string;
  total_years_experience: string;
  expected_salary: string;
  remote_preference: string;
  job_type_preference: string;
  work_authorization: string;
  relocation_willingness: string;
}

const EMPTY_FORM: FormData = {
  first_name: "",
  last_name: "",
  current_title: "",
  address: "",
  city: "",
  state: "",
  zip_code: "",
  phone: "",
  total_years_experience: "",
  expected_salary: "",
  remote_preference: "",
  job_type_preference: "",
  work_authorization: "",
  relocation_willingness: "",
};

interface CrossJob {
  job_id: number;
  title: string;
  location: string | null;
  ips_score: number;
  explanation: string;
  already_applied: boolean;
}

interface Branding {
  colors: Record<string, string>;
  fonts?: { heading?: string; body?: string };
}

interface ApplicationModalProps {
  slug: string;
  jobId: number;
  jobTitle: string;
  company: string | null;
  location: string | null;
  branding: Branding;
  onClose: () => void;
}

const STORAGE_KEY = "winnow_apply_session";

function saveSession(data: { sessionToken: string; jobId: number; jobTitle: string; slug: string }) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {}
}

function clearSession() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
}

export function loadSavedSession(): { sessionToken: string; jobId: number; jobTitle: string; slug: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export default function ApplicationModal({
  slug,
  jobId,
  jobTitle,
  company,
  location,
  branding,
  onClose,
}: ApplicationModalProps) {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Resume step
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Form step
  const [form, setForm] = useState<FormData>({ ...EMPTY_FORM });
  const [existingApplicant, setExistingApplicant] = useState(false);
  const [completeness, setCompleteness] = useState(0);
  const [canSubmit, setCanSubmit] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  // Cross-job
  const [crossJobs, setCrossJobs] = useState<CrossJob[]>([]);
  const [crossJobPitch, setCrossJobPitch] = useState("");
  const [selectedCrossJobs, setSelectedCrossJobs] = useState<Set<number>>(new Set());
  const [crossJobsFetched, setCrossJobsFetched] = useState(false);

  // Done step
  const [ipsScore, setIpsScore] = useState<number | null>(null);
  const [additionalCount, setAdditionalCount] = useState(0);
  const [doneMessage, setDoneMessage] = useState("");

  const primary = branding.colors.primary || "#2563eb";
  const headingFont = branding.fonts?.heading || "Inter, sans-serif";

  // Scroll error into view
  useEffect(() => {
    if (error && errorRef.current) {
      errorRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [error]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Fetch cross-job recommendations when completeness >= 70
  useEffect(() => {
    if (completeness >= 70 && sessionToken && !crossJobsFetched) {
      setCrossJobsFetched(true);
      fetch(`${API}/api/public/apply/cross-jobs/${sessionToken}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data) {
            setCrossJobs(data.matches || []);
            setCrossJobPitch(data.pitch_message || "");
          }
        })
        .catch(() => {});
    }
  }, [completeness, sessionToken, crossJobsFetched]);

  function updateForm(field: keyof FormData, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  // -- Step handlers --

  async function handleStart() {
    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/public/apply/${slug}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: jobId,
          email: email.trim(),
          source_url: window.location.href,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to start application");
      }
      const data = await res.json();
      setSessionToken(data.session_token);
      saveSession({ sessionToken: data.session_token, jobId, jobTitle, slug });
      setStep("resume");
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    }
    setLoading(false);
  }

  async function handleResumeUpload(file: File) {
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be under 10MB");
      return;
    }
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "doc", "docx", "txt"].includes(ext || "")) {
      setError("Supported formats: PDF, DOC, DOCX, TXT");
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setError("");

    // Animate progress: fast to ~40%, slow to ~85%, then hold
    progressRef.current = setInterval(() => {
      setUploadProgress(prev => {
        if (prev < 40) return prev + 3;
        if (prev < 70) return prev + 1.5;
        if (prev < 85) return prev + 0.5;
        return prev;
      });
    }, 200);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API}/api/public/apply/resume/${sessionToken}`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to upload resume");
      }
      const data = await res.json();

      // Jump to 100%
      if (progressRef.current) clearInterval(progressRef.current);
      setUploadProgress(100);

      setCompleteness(data.completeness_score);

      // Populate form from prefilled data
      if (data.prefilled_form) {
        setForm(prev => {
          const next = { ...prev };
          for (const [key, val] of Object.entries(data.prefilled_form)) {
            if (key in next && val != null && val !== "") {
              (next as any)[key] = String(val);
            }
          }
          return next;
        });
      }

      setExistingApplicant(data.existing_applicant || false);
      // Brief pause at 100% before advancing
      await new Promise(r => setTimeout(r, 300));
      setStep("form");
    } catch (e: any) {
      setError(e.message || "Upload failed");
    }
    if (progressRef.current) clearInterval(progressRef.current);
    setUploading(false);
  }

  async function handleFormSubmit() {
    // Validate required fields
    if (!form.first_name.trim() || !form.last_name.trim() || !form.current_title.trim() || !form.phone.trim() || !form.total_years_experience) {
      setError("Please fill in all required fields");
      return;
    }

    setFormSubmitting(true);
    setError("");
    try {
      const payload: any = {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        current_title: form.current_title.trim(),
        phone: form.phone.trim(),
        total_years_experience: parseInt(form.total_years_experience, 10) || 0,
      };
      // Optional fields
      if (form.address.trim()) payload.address = form.address.trim();
      if (form.city.trim()) payload.city = form.city.trim();
      if (form.state.trim()) payload.state = form.state.trim().toUpperCase();
      if (form.zip_code.trim()) payload.zip_code = form.zip_code.trim();
      if (form.expected_salary) payload.expected_salary = parseInt(form.expected_salary, 10);
      if (form.remote_preference) payload.remote_preference = form.remote_preference;
      if (form.job_type_preference) payload.job_type_preference = form.job_type_preference;
      if (form.work_authorization.trim()) payload.work_authorization = form.work_authorization.trim();
      if (form.relocation_willingness) payload.relocation_willingness = form.relocation_willingness;

      const res = await fetch(`${API}/api/public/apply/form/${sessionToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to submit form");
      }
      const data = await res.json();
      setCompleteness(data.completeness_score);
      setCanSubmit(data.can_submit);

      // Always submit after form data is saved
      await handleSubmit();
    } catch (e: any) {
      setError(e.message || "Form submission failed");
    }
    setFormSubmitting(false);
  }

  async function handleSubmit() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/public/apply/submit/${sessionToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apply_to_additional: Array.from(selectedCrossJobs) }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Submission failed");
      }
      const data = await res.json();
      setIpsScore(data.ips_score);
      setAdditionalCount(data.additional_applications?.length || 0);
      setDoneMessage(data.message);
      clearSession();
      setStep("done");
    } catch (e: any) {
      setError(e.message || "Submission failed");
    }
    setLoading(false);
  }

  function toggleCrossJob(id: number) {
    setSelectedCrossJobs(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const inputClasses = "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:outline-none";

  // -- Render --

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative bg-white w-full sm:max-w-lg sm:rounded-2xl shadow-2xl flex flex-col max-h-[100dvh] sm:max-h-[90vh] overflow-hidden"
        style={{ fontFamily: branding.fonts?.body || "Inter, sans-serif" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b shrink-0 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-gray-900 truncate" style={{ fontFamily: headingFont }}>
              {step === "done" ? "Application Submitted!" : `Apply: ${jobTitle}`}
            </h2>
            {company && step !== "done" && (
              <p className="text-sm text-gray-500 mt-0.5">{company}{location ? ` · ${location}` : ""}</p>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg shrink-0" aria-label="Close">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Completeness bar (form step) */}
        {step === "form" && (
          <div className="px-5 py-2 border-b shrink-0">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Profile completeness</span>
              <span className="font-medium" style={{ color: completeness >= 70 ? "#16a34a" : primary }}>{completeness}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${completeness}%`, backgroundColor: completeness >= 70 ? "#16a34a" : primary }}
              />
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {/* === EMAIL STEP === */}
          {step === "email" && (
            <div className="p-5 space-y-4">
              <p className="text-sm text-gray-600">
                Enter your email and upload your resume to get started.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email <span className="text-red-500">*</span></label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className={inputClasses}
                  style={{ ["--tw-ring-color" as any]: primary + "40", borderColor: email ? primary : undefined }}
                  onKeyDown={e => { if (e.key === "Enter" && email.trim()) handleStart(); }}
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          )}

          {/* === RESUME STEP === */}
          {step === "resume" && (
            <div className="p-5 space-y-4">
              <p className="text-sm text-gray-600">
                Upload your resume and we'll pre-fill your application.
              </p>

              {/* Drop zone */}
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  dragOver ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                }`}
                style={dragOver ? { borderColor: primary, backgroundColor: primary + "10" } : {}}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => {
                  e.preventDefault();
                  setDragOver(false);
                  const file = e.dataTransfer.files[0];
                  if (file) handleResumeUpload(file);
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  className="hidden"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleResumeUpload(file);
                  }}
                />
                {uploading ? (
                  <div className="space-y-3">
                    <p className="text-2xl font-bold" style={{ color: primary }}>{Math.round(uploadProgress)}%</p>
                    <div className="w-48 mx-auto h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-200"
                        style={{ width: `${uploadProgress}%`, backgroundColor: primary }}
                      />
                    </div>
                    <p className="text-sm font-medium text-gray-700">Parsing your resume...</p>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm font-medium text-gray-700">Drop your resume here or click to browse</p>
                    <p className="text-xs text-gray-400 mt-1">PDF, DOC, DOCX, or TXT (max 10MB)</p>
                  </>
                )}
              </div>

              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          )}

          {/* === FORM STEP === */}
          {step === "form" && (
            <div className="p-5 space-y-4">
              {/* Error at top of form */}
              {error && (
                <div ref={errorRef} className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {/* Returning applicant banner */}
              {existingApplicant && (
                <div className="flex items-start gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-green-800">Welcome back!</p>
                    <p className="text-xs text-green-700 mt-0.5">
                      We have your info on file. Please review and update anything that's changed.
                    </p>
                  </div>
                </div>
              )}

              {/* Name row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">First Name <span className="text-red-500">*</span></label>
                  <input type="text" value={form.first_name} onChange={e => updateForm("first_name", e.target.value)} className={inputClasses} placeholder="First name" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Last Name <span className="text-red-500">*</span></label>
                  <input type="text" value={form.last_name} onChange={e => updateForm("last_name", e.target.value)} className={inputClasses} placeholder="Last name" />
                </div>
              </div>

              {/* Current Job Title */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Current / Most Recent Job Title <span className="text-red-500">*</span></label>
                <input type="text" value={form.current_title} onChange={e => updateForm("current_title", e.target.value)} className={inputClasses} placeholder="e.g. Software Engineer" />
              </div>

              {/* Address */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Address</label>
                <input type="text" value={form.address} onChange={e => updateForm("address", e.target.value)} className={inputClasses} placeholder="Street address" />
              </div>

              {/* City / State / Zip row */}
              <div className="grid grid-cols-6 gap-3">
                <div className="col-span-3">
                  <label className="block text-xs font-medium text-gray-700 mb-1">City</label>
                  <input type="text" value={form.city} onChange={e => updateForm("city", e.target.value)} className={inputClasses} placeholder="City" />
                </div>
                <div className="col-span-1">
                  <label className="block text-xs font-medium text-gray-700 mb-1">State</label>
                  <input type="text" value={form.state} onChange={e => updateForm("state", e.target.value)} className={inputClasses} placeholder="TX" maxLength={2} />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-gray-700 mb-1">Zip</label>
                  <input type="text" value={form.zip_code} onChange={e => updateForm("zip_code", e.target.value)} className={inputClasses} placeholder="78701" />
                </div>
              </div>

              {/* Phone */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Phone <span className="text-red-500">*</span></label>
                <input type="tel" value={form.phone} onChange={e => updateForm("phone", e.target.value)} className={inputClasses} placeholder="(555) 123-4567" />
              </div>

              {/* Experience / Salary row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Total Years of Experience <span className="text-red-500">*</span></label>
                  <input type="number" value={form.total_years_experience} onChange={e => updateForm("total_years_experience", e.target.value)} className={inputClasses} placeholder="5" min={0} max={99} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Expected Salary</label>
                  <input type="number" value={form.expected_salary} onChange={e => updateForm("expected_salary", e.target.value)} className={inputClasses} placeholder="75000" min={0} />
                </div>
              </div>

              {/* Remote / Job Type row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Remote Preference</label>
                  <select value={form.remote_preference} onChange={e => updateForm("remote_preference", e.target.value)} className={inputClasses}>
                    <option value="">Select...</option>
                    <option value="remote">Remote</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">Onsite</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Job Type Preference</label>
                  <select value={form.job_type_preference} onChange={e => updateForm("job_type_preference", e.target.value)} className={inputClasses}>
                    <option value="">Select...</option>
                    <option value="permanent">Permanent</option>
                    <option value="contract">Contract</option>
                    <option value="temporary">Temporary</option>
                  </select>
                </div>
              </div>

              {/* Work Authorization */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Work Authorization</label>
                <input type="text" value={form.work_authorization} onChange={e => updateForm("work_authorization", e.target.value)} className={inputClasses} placeholder="US Citizen, H-1B, etc." />
              </div>

              {/* Relocation */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Willing to Relocate</label>
                <select value={form.relocation_willingness} onChange={e => updateForm("relocation_willingness", e.target.value)} className={inputClasses}>
                  <option value="">Select...</option>
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </div>

              {/* Cross-job recommendations */}
              {crossJobs.length > 0 && (
                <div className="border rounded-xl overflow-hidden">
                  <div className="bg-gray-50 px-3 py-2 border-b">
                    <p className="text-xs font-medium text-gray-600">
                      <Briefcase className="w-3 h-3 inline mr-1" />
                      {crossJobPitch || "You might also be a great fit for:"}
                    </p>
                  </div>
                  <div className="divide-y">
                    {crossJobs.map(job => (
                      <label
                        key={job.job_id}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedCrossJobs.has(job.job_id)}
                          onChange={() => toggleCrossJob(job.job_id)}
                          className="rounded"
                          style={{ accentColor: primary }}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-800 truncate">{job.title}</p>
                          {job.location && (
                            <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                              <MapPin className="w-3 h-3" />{job.location}
                            </p>
                          )}
                        </div>
                        {job.ips_score > 0 && (
                          <span
                            className="text-xs font-bold px-2 py-0.5 rounded-full text-white shrink-0"
                            style={{ backgroundColor: job.ips_score >= 80 ? "#16a34a" : job.ips_score >= 60 ? "#eab308" : "#9ca3af" }}
                          >
                            {job.ips_score}%
                          </span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}

          {/* === DONE STEP === */}
          {step === "done" && (
            <div className="p-6 text-center space-y-4">
              <CheckCircle2 className="w-16 h-16 mx-auto text-green-500" />
              <h3 className="text-xl font-bold text-gray-900" style={{ fontFamily: headingFont }}>
                Application Submitted!
              </h3>
              {ipsScore != null && ipsScore > 0 && (
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-full">
                  <span className="text-sm text-gray-600">Match Score:</span>
                  <span
                    className="text-lg font-bold"
                    style={{ color: ipsScore >= 80 ? "#16a34a" : ipsScore >= 60 ? "#eab308" : "#6b7280" }}
                  >
                    {ipsScore}%
                  </span>
                </div>
              )}
              {additionalCount > 0 && (
                <p className="text-sm text-gray-600">
                  Also applied to {additionalCount} additional role{additionalCount !== 1 ? "s" : ""}
                </p>
              )}
              {doneMessage && <p className="text-sm text-gray-600">{doneMessage}</p>}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="px-5 py-3 border-t shrink-0 flex gap-2">
          {step === "email" && (
            <button
              onClick={handleStart}
              disabled={loading || !email.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-white font-medium text-sm transition-opacity disabled:opacity-60"
              style={{ backgroundColor: primary }}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
              Start Application
            </button>
          )}

          {step === "form" && (
            <button
              onClick={handleFormSubmit}
              disabled={formSubmitting || loading}
              className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-white font-medium text-sm transition-opacity disabled:opacity-60"
              style={{ backgroundColor: primary }}
            >
              {(formSubmitting || loading) ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Submit Application{selectedCrossJobs.size > 0 ? ` (+${selectedCrossJobs.size})` : ""}
            </button>
          )}

          {step === "done" && (
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-lg text-white font-medium text-sm"
              style={{ backgroundColor: primary }}
            >
              Browse More Jobs
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
