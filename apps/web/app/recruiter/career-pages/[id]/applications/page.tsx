"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileText, ChevronDown, ChevronUp } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface Application {
  id: string;
  email: string | null;
  applicant_name: string | null;
  job_id: number;
  job_title: string | null;
  status: string;
  completeness_score: number;
  ips_score: number | null;
  started_at: string | null;
  completed_at: string | null;
}

interface ApplicationDetail {
  id: string;
  email: string | null;
  applicant_name: string | null;
  job_id: number;
  job_title: string | null;
  status: string;
  completeness_score: number;
  ips_score: number | null;
  ips_breakdown: Record<string, any> | null;
  resume_file_url: string | null;
  resume_parsed_data: Record<string, any> | null;
  question_responses: Record<string, any> | null;
  source_url: string | null;
  started_at: string | null;
  completed_at: string | null;
}

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  started: "bg-amber-100 text-amber-700",
  resume_uploaded: "bg-amber-100 text-amber-700",
  profile_building: "bg-blue-100 text-blue-700",
  abandoned: "bg-red-100 text-red-700",
};

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function ApplicationsPage() {
  const params = useParams();
  const pageId = params.id as string;

  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    const url = statusFilter
      ? `${API}/api/career-pages/${pageId}/applications?status_filter=${statusFilter}`
      : `${API}/api/career-pages/${pageId}/applications`;
    fetch(url, { credentials: "include" })
      .then(res => res.ok ? res.json() : { applications: [] })
      .then(data => setApps(data.applications || []))
      .finally(() => setLoading(false));
  }, [pageId, statusFilter]);

  async function toggleDetail(appId: string) {
    if (expandedId === appId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(appId);
    setDetailLoading(true);
    try {
      const res = await fetch(`${API}/api/career-pages/${pageId}/applications/${appId}`, { credentials: "include" });
      if (res.ok) setDetail(await res.json());
    } catch {}
    setDetailLoading(false);
  }

  if (loading) return <div className="flex justify-center p-12"><div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full" /></div>;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <Link href="/recruiter/career-pages" className="flex items-center gap-1 text-sm text-blue-600 hover:underline mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to Career Pages
        </Link>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
          <select
            value={statusFilter}
            onChange={e => { setLoading(true); setStatusFilter(e.target.value); }}
            className="px-3 py-2 border rounded-lg text-sm"
          >
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="started">Started</option>
            <option value="resume_uploaded">Resume Uploaded</option>
            <option value="profile_building">Profile Building</option>
            <option value="abandoned">Abandoned</option>
          </select>
        </div>
      </div>

      {apps.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center">
          <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No applications yet</h3>
          <p className="text-gray-600">Applications will appear here as candidates apply through your career page.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Position</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-center">Score</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {apps.map(app => (
                <>
                  <tr
                    key={app.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => toggleDetail(app.id)}
                  >
                    <td className="px-4 py-3 font-medium text-gray-900">{app.applicant_name || "—"}</td>
                    <td className="px-4 py-3 text-gray-600">{app.email || "—"}</td>
                    <td className="px-4 py-3 text-gray-600">{app.job_title || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full ${STATUS_STYLES[app.status] || "bg-gray-100 text-gray-600"}`}>
                        {app.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {app.ips_score != null ? (
                        <span className={`font-bold ${app.ips_score >= 80 ? "text-green-600" : app.ips_score >= 60 ? "text-yellow-600" : "text-gray-500"}`}>
                          {app.ips_score}%
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{formatDate(app.completed_at || app.started_at)}</td>
                    <td className="px-4 py-3">
                      {expandedId === app.id ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                    </td>
                  </tr>
                  {expandedId === app.id && (
                    <tr key={`${app.id}-detail`}>
                      <td colSpan={7} className="bg-gray-50 px-6 py-4">
                        {detailLoading ? (
                          <div className="flex justify-center py-4"><div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" /></div>
                        ) : detail ? (
                          <div className="grid grid-cols-2 gap-6 text-sm">
                            <div>
                              <h4 className="font-semibold text-gray-800 mb-2">Application Info</h4>
                              <dl className="space-y-1">
                                <div className="flex gap-2"><dt className="text-gray-500 w-32">Completeness</dt><dd>{detail.completeness_score}%</dd></div>
                                {detail.ips_score != null && <div className="flex gap-2"><dt className="text-gray-500 w-32">IPS Score</dt><dd>{detail.ips_score}%</dd></div>}
                                {detail.source_url && <div className="flex gap-2"><dt className="text-gray-500 w-32">Source URL</dt><dd className="truncate max-w-xs">{detail.source_url}</dd></div>}
                                {detail.resume_file_url && (
                                  <div className="flex gap-2">
                                    <dt className="text-gray-500 w-32">Resume</dt>
                                    <dd><a href={detail.resume_file_url} target="_blank" className="text-blue-600 hover:underline">View resume</a></dd>
                                  </div>
                                )}
                              </dl>
                            </div>
                            <div>
                              <h4 className="font-semibold text-gray-800 mb-2">Parsed Resume Data</h4>
                              {detail.resume_parsed_data ? (
                                <dl className="space-y-1">
                                  {Object.entries(detail.resume_parsed_data)
                                    .filter(([k]) => !["raw_text"].includes(k))
                                    .slice(0, 10)
                                    .map(([k, v]) => (
                                      <div key={k} className="flex gap-2">
                                        <dt className="text-gray-500 w-32 capitalize">{k.replace(/_/g, " ")}</dt>
                                        <dd className="truncate max-w-xs">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                                      </div>
                                    ))}
                                </dl>
                              ) : (
                                <p className="text-gray-400">No resume data</p>
                              )}
                            </div>
                            {detail.ips_breakdown && Object.keys(detail.ips_breakdown).length > 0 && (
                              <div className="col-span-2">
                                <h4 className="font-semibold text-gray-800 mb-2">IPS Breakdown</h4>
                                <div className="flex flex-wrap gap-3">
                                  {Object.entries(detail.ips_breakdown).map(([k, v]) => (
                                    <div key={k} className="bg-white border rounded-lg px-3 py-2">
                                      <span className="text-xs text-gray-500 capitalize">{k.replace(/_/g, " ")}</span>
                                      <div className="font-bold text-gray-900">{String(v)}</div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {detail.question_responses && Object.keys(detail.question_responses).length > 0 && (
                              <div className="col-span-2">
                                <h4 className="font-semibold text-gray-800 mb-2">Form Responses</h4>
                                {detail.question_responses.form_data ? (
                                  <dl className="grid grid-cols-2 gap-1">
                                    {Object.entries(detail.question_responses.form_data).map(([k, v]) => (
                                      <div key={k} className="flex gap-2">
                                        <dt className="text-gray-500 capitalize">{k.replace(/_/g, " ")}</dt>
                                        <dd>{String(v)}</dd>
                                      </div>
                                    ))}
                                  </dl>
                                ) : (
                                  <pre className="text-xs bg-white border rounded p-2 overflow-auto max-h-40">
                                    {JSON.stringify(detail.question_responses, null, 2)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        ) : (
                          <p className="text-gray-500">Failed to load details</p>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
