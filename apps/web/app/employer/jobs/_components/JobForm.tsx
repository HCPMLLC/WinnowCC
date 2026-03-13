"use client";

import { useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";


export interface JobFormData {
  title: string;
  description: string;
  requirements: string;
  nice_to_haves: string;
  location: string;
  remote_policy: string;
  employment_type: string;
  salary_min: string;
  salary_max: string;
  salary_currency: string;
  equity_offered: boolean;
  bill_rate: string;
  application_email: string;
  application_url: string;
  job_id_external: string;
  start_date: string;
  close_date: string;
  job_category: string;
  client_company_name: string;
  department: string;
  certifications_required: string[];
  job_type: string;
}

const EMPTY_FORM: JobFormData = {
  title: "",
  description: "",
  requirements: "",
  nice_to_haves: "",
  location: "",
  remote_policy: "",
  employment_type: "",
  salary_min: "",
  salary_max: "",
  salary_currency: "USD",
  equity_offered: false,
  bill_rate: "",
  application_email: "",
  application_url: "",
  job_id_external: "",
  start_date: "",
  close_date: "",
  job_category: "",
  client_company_name: "",
  department: "",
  certifications_required: [],
  job_type: "",
};

interface JobFormProps {
  initialData?: Partial<JobFormData>;
  mode: "create" | "edit";
  jobId?: number;
  onSuccess: (job: { id: number }) => void;
  onCancel: () => void;
}

export default function JobForm({
  initialData,
  mode,
  jobId,
  onSuccess,
  onCancel,
}: JobFormProps) {
  const [formData, setFormData] = useState<JobFormData>({
    ...EMPTY_FORM,
    ...initialData,
    certifications_required:
      initialData?.certifications_required ?? EMPTY_FORM.certifications_required,
  });
  const [certInput, setCertInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  function addCertification() {
    const val = certInput.trim();
    if (val && !formData.certifications_required.includes(val)) {
      setFormData({
        ...formData,
        certifications_required: [...formData.certifications_required, val],
      });
      setCertInput("");
    }
  }

  function removeCertification(index: number) {
    setFormData({
      ...formData,
      certifications_required: formData.certifications_required.filter(
        (_, i) => i !== index,
      ),
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const payload = {
        ...formData,
        salary_min: formData.salary_min
          ? parseInt(formData.salary_min)
          : null,
        salary_max: formData.salary_max
          ? parseInt(formData.salary_max)
          : null,
        bill_rate: formData.bill_rate
          ? parseInt(formData.bill_rate)
          : null,
        location: formData.location || null,
        remote_policy: formData.remote_policy || null,
        employment_type: formData.employment_type || null,
        application_email: formData.application_email || null,
        application_url: formData.application_url || null,
        job_id_external: formData.job_id_external || null,
        start_date: formData.start_date || null,
        close_date: formData.close_date || null,
        job_category: formData.job_category || null,
        client_company_name: formData.client_company_name || null,
        department: formData.department || null,
        certifications_required:
          formData.certifications_required.length > 0
            ? formData.certifications_required
            : null,
        job_type: formData.job_type || null,
      };

      const url =
        mode === "edit"
          ? `${API_BASE}/api/employer/jobs/${jobId}`
          : `${API_BASE}/api/employer/jobs`;

      const res = await fetch(url, {
        method: mode === "edit" ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(
          data.detail ||
            (mode === "edit" ? "Failed to update job" : "Failed to create job"),
        );
      }

      const job = await res.json();
      onSuccess({ id: job.id });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  }

  const fmtUSD = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

  async function fetchSalaryEstimate() {
    if (formData.salary_min || formData.salary_max) return;
    if (!formData.title.trim()) return;
    try {
      const params = new URLSearchParams({ title: formData.title.trim() });
      if (formData.location.trim()) {
        params.set("location", formData.location.trim());
      }
      const res = await fetch(
        `${API_BASE}/api/employer/jobs/salary-estimate?${params}`,
        { credentials: "include" },
      );
      if (!res.ok) return;
      const data = await res.json();
      setFormData((prev) => ({
        ...prev,
        salary_min: String(data.salary_min),
        salary_max: String(data.salary_max),
      }));
    } catch {
      // silently ignore — salary estimate is best-effort
    }
  }

  function salaryDisplay(raw: string): string {
    const n = parseInt(raw.replace(/\D/g, ""), 10);
    return Number.isNaN(n) || n === 0 ? "" : fmtUSD.format(n);
  }

  function salaryChange(raw: string): string {
    return raw.replace(/\D/g, "");
  }

  const inputClass =
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

  return (
    <>
      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        {/* Job ID / Requisition # */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Job ID / Requisition #
          </label>
          <input
            type="text"
            value={formData.job_id_external}
            onChange={(e) =>
              setFormData({ ...formData, job_id_external: e.target.value })
            }
            className={inputClass}
            placeholder="REQ-2026-001"
          />
        </div>

        {/* Row: Job Title + Department */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Job Title *
            </label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) =>
                setFormData({ ...formData, title: e.target.value })
              }
              onBlur={fetchSalaryEstimate}
              className={inputClass}
              placeholder="Senior Software Engineer"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Department
            </label>
            <input
              type="text"
              value={formData.department}
              onChange={(e) =>
                setFormData({ ...formData, department: e.target.value })
              }
              className={inputClass}
              placeholder="Engineering"
            />
          </div>
        </div>

        {/* Row: Job Type + Job Category */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Job Type
            </label>
            <select
              value={formData.job_type}
              onChange={(e) =>
                setFormData({ ...formData, job_type: e.target.value })
              }
              className={inputClass}
            >
              <option value="">Select type...</option>
              <option value="permanent">Permanent</option>
              <option value="contract">Contract</option>
              <option value="temporary">Temporary</option>
              <option value="seasonal">Seasonal</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Job Category
            </label>
            <input
              type="text"
              value={formData.job_category}
              onChange={(e) =>
                setFormData({ ...formData, job_category: e.target.value })
              }
              placeholder="e.g. Engineering, Project Management, IT"
              className={inputClass}
            />
          </div>
        </div>

        {/* Client */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Client
          </label>
          <input
            type="text"
            value={formData.client_company_name}
            onChange={(e) =>
              setFormData({ ...formData, client_company_name: e.target.value })
            }
            placeholder="Client or hiring organization"
            className={inputClass}
          />
        </div>

        {/* Row: Location + Remote Policy */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Location
            </label>
            <input
              type="text"
              value={formData.location}
              onChange={(e) =>
                setFormData({ ...formData, location: e.target.value })
              }
              onBlur={fetchSalaryEstimate}
              className={inputClass}
              placeholder="San Francisco, CA"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Remote Policy
            </label>
            <select
              value={formData.remote_policy}
              onChange={(e) =>
                setFormData({ ...formData, remote_policy: e.target.value })
              }
              className={inputClass}
            >
              <option value="">Select...</option>
              <option value="on-site">On-site</option>
              <option value="hybrid">Hybrid</option>
              <option value="remote">Remote</option>
            </select>
          </div>
        </div>

        {/* Row: Start Date + Application Deadline */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Start Date
            </label>
            <input
              type="date"
              value={formData.start_date}
              onChange={(e) =>
                setFormData({ ...formData, start_date: e.target.value })
              }
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Application Deadline
            </label>
            <input
              type="date"
              value={formData.close_date}
              onChange={(e) =>
                setFormData({ ...formData, close_date: e.target.value })
              }
              className={inputClass}
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Job Description *
          </label>
          <textarea
            required
            value={formData.description}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            rows={6}
            className={inputClass}
            placeholder="Describe the role, responsibilities, and what makes it exciting..."
          />
        </div>

        {/* Minimum Required Experience */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Minimum Required Experience
          </label>
          <textarea
            value={formData.requirements}
            onChange={(e) =>
              setFormData({ ...formData, requirements: e.target.value })
            }
            rows={4}
            className={inputClass}
            placeholder="Required qualifications, skills, and experience..."
          />
        </div>

        {/* Preferred Experience */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Preferred Experience
          </label>
          <textarea
            value={formData.nice_to_haves}
            onChange={(e) =>
              setFormData({ ...formData, nice_to_haves: e.target.value })
            }
            rows={3}
            className={inputClass}
            placeholder="Preferred qualifications and experience..."
          />
        </div>

        {/* Row: Employment Type + Salary Range */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Employment Type
            </label>
            <select
              value={formData.employment_type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  employment_type: e.target.value,
                })
              }
              className={inputClass}
            >
              <option value="">Select...</option>
              <option value="full-time">Full-time</option>
              <option value="part-time">Part-time</option>
              <option value="contract">Contract</option>
              <option value="internship">Internship</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Salary Min (USD)
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={salaryDisplay(formData.salary_min)}
              onChange={(e) =>
                setFormData({ ...formData, salary_min: salaryChange(e.target.value) })
              }
              className={inputClass}
              placeholder="$100,000"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Salary Max (USD)
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={salaryDisplay(formData.salary_max)}
              onChange={(e) =>
                setFormData({ ...formData, salary_max: salaryChange(e.target.value) })
              }
              className={inputClass}
              placeholder="$150,000"
            />
          </div>
        </div>

        {/* Bill Rate */}
        <div className="max-w-xs">
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Bill Rate ($/hr)
          </label>
          <input
            type="text"
            inputMode="numeric"
            value={salaryDisplay(formData.bill_rate)}
            onChange={(e) =>
              setFormData({ ...formData, bill_rate: salaryChange(e.target.value) })
            }
            className={inputClass}
            placeholder="$85"
          />
        </div>

        {/* Application Email + URL */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Application Email
            </label>
            <input
              type="email"
              value={formData.application_email}
              onChange={(e) =>
                setFormData({ ...formData, application_email: e.target.value })
              }
              className={inputClass}
              placeholder="jobs@company.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Application URL
            </label>
            <input
              type="url"
              value={formData.application_url}
              onChange={(e) =>
                setFormData({ ...formData, application_url: e.target.value })
              }
              className={inputClass}
              placeholder="https://company.com/careers/apply"
            />
          </div>
        </div>

        {/* Certifications */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Required Certifications
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={certInput}
              onChange={(e) => setCertInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCertification();
                }
              }}
              className={`flex-1 ${inputClass}`}
              placeholder="e.g., PMP, AWS Solutions Architect"
            />
            <button
              type="button"
              onClick={addCertification}
              className="rounded-md bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-300"
            >
              Add
            </button>
          </div>
          {formData.certifications_required.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {formData.certifications_required.map((cert, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700"
                >
                  {cert}
                  <button
                    type="button"
                    onClick={() => removeCertification(i)}
                    className="text-slate-400 hover:text-red-600"
                  >
                    &times;
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-6 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 rounded-md bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isLoading
              ? mode === "edit"
                ? "Saving..."
                : "Creating..."
              : mode === "edit"
                ? "Save Changes"
                : "Create Job (Draft)"}
          </button>
        </div>
      </form>
    </>
  );
}
