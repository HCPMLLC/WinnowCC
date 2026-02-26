"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchAuthMe } from "../../lib/auth";

const API =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type JobForm = {
  id: number;
  job_id: number;
  original_filename: string;
  file_type: string;
  form_type: string;
  is_parsed: boolean;
  total_fields: number | null;
  auto_fillable: number | null;
  needs_manual: number | null;
  created_at: string | null;
};

export default function AdminFormsPage() {
  const router = useRouter();
  const [jobId, setJobId] = useState("");
  const [forms, setForms] = useState<JobForm[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchAuthMe().then((u) => {
      if (!u) router.push("/login");
    });
  }, [router]);

  async function loadForms() {
    if (!jobId) return;
    setLoading(true);
    const res = await fetch(`${API}/api/jobs/${jobId}/forms`, {
      credentials: "include",
    });
    if (res.ok) {
      setForms(await res.json());
    }
    setLoading(false);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !jobId) return;

    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch(`${API}/api/jobs/${jobId}/forms`, {
      method: "POST",
      credentials: "include",
      body: fd,
    });
    if (res.ok) {
      await loadForms();
    }
    setUploading(false);
    e.target.value = "";
  }

  async function handleDelete(formId: number) {
    await fetch(`${API}/api/jobs/${jobId}/forms/${formId}`, {
      method: "DELETE",
      credentials: "include",
    });
    await loadForms();
  }

  async function handleReparse(formId: number) {
    await fetch(`${API}/api/jobs/${jobId}/forms/${formId}/reparse`, {
      method: "POST",
      credentials: "include",
    });
    await loadForms();
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Employer Forms Management
        </h1>

        {/* Job ID selector */}
        <div className="bg-white rounded-lg shadow-sm border p-4 mb-6">
          <div className="flex gap-3 items-end">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Job ID
              </label>
              <input
                className="border rounded-md px-3 py-2 text-sm w-32"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                placeholder="e.g. 42"
                type="number"
              />
            </div>
            <button
              onClick={loadForms}
              disabled={!jobId}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              Load Forms
            </button>
            <div>
              <label className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 cursor-pointer inline-block">
                {uploading ? "Uploading..." : "Upload Form"}
                <input
                  type="file"
                  accept=".docx,.pdf"
                  onChange={handleUpload}
                  className="hidden"
                  disabled={!jobId || uploading}
                />
              </label>
            </div>
          </div>
        </div>

        {/* Forms list */}
        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : (
          <div className="space-y-3">
            {forms.length === 0 && jobId && (
              <p className="text-gray-500 text-sm">
                No forms found for this job.
              </p>
            )}
            {forms.map((form) => (
              <div
                key={form.id}
                className="bg-white rounded-lg shadow-sm border p-4"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      {form.original_filename}
                    </h3>
                    <p className="text-sm text-gray-600">
                      Type: {form.form_type} | Format: {form.file_type} |{" "}
                      {form.is_parsed ? "Parsed" : "Not parsed"}
                    </p>
                    {form.is_parsed && (
                      <p className="text-xs text-gray-400 mt-1">
                        Fields: {form.total_fields ?? 0} total,{" "}
                        {form.auto_fillable ?? 0} auto-fillable,{" "}
                        {form.needs_manual ?? 0} manual
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleReparse(form.id)}
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      Re-parse
                    </button>
                    <button
                      onClick={() => handleDelete(form.id)}
                      className="text-sm text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
