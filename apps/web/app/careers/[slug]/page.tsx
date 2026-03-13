"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { MapPin, DollarSign, Loader2, Briefcase, Search, MessageSquare, Building2, Calendar, X, ExternalLink, Clock, ChevronRight } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface CareerPageData {
  slug: string;
  page_title: string | null;
  meta_description: string | null;
  config: {
    branding: {
      colors: Record<string, string>;
      logo_url?: string;
      logo_alt?: string;
      website_url?: string;
      fonts?: { heading?: string; body?: string };
    };
    layout: {
      hero_style: string;
      gradient_angle?: number;
      hero_image_url?: string;
      hero_overlay_opacity?: number;
      job_display: string;
      show_ips_preview: boolean;
      show_salary_ranges: boolean;
    };
    sections: Array<{ type: string; enabled: boolean; config: Record<string, any> }>;
    sieve: { enabled: boolean; name: string; welcome_message: string };
  };
}

interface JobData {
  id: number;
  title: string;
  company: string | null;
  job_id_external: string | null;
  location: string | null;
  location_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  application_deadline: string | null;
  posted_at: string;
}

interface JobDetail extends JobData {
  description_html: string | null;
  description_text: string;
  url: string | null;
}

export default function PublicCareerPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const slug = params.slug as string;
  const isPreview = searchParams.get("preview") === "true";

  const [pageData, setPageData] = useState<CareerPageData | null>(null);
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [page, setPage] = useState(1);

  // Job detail modal state
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [jobLoading, setJobLoading] = useState(false);

  useEffect(() => {
    const previewParam = isPreview ? "?preview=true" : "";
    fetch(`${API}/api/public/career-pages/${slug}${previewParam}`)
      .then(res => { if (!res.ok) throw new Error(); return res.json(); })
      .then(setPageData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [slug, isPreview]);

  useEffect(() => {
    if (!pageData) return;
    const qp = new URLSearchParams({ page: String(page), page_size: "12" });
    if (search) qp.set("search", search);
    if (location) qp.set("location", location);
    if (isPreview) qp.set("preview", "true");

    fetch(`${API}/api/public/career-pages/${slug}/jobs?${qp}`)
      .then(res => res.ok ? res.json() : { jobs: [], total: 0 })
      .then(data => { setJobs(data.jobs); setTotalJobs(data.total); });
  }, [slug, pageData, page, search, location, isPreview]);

  const openJobDetail = useCallback(async (jobId: number) => {
    setJobLoading(true);
    setSelectedJob(null);
    try {
      const previewParam = isPreview ? "?preview=true" : "";
      const res = await fetch(`${API}/api/public/career-pages/${slug}/jobs/${jobId}${previewParam}`);
      if (res.ok) {
        const detail = await res.json();
        setSelectedJob(detail);
      }
    } catch { /* ignore */ }
    setJobLoading(false);
  }, [slug, isPreview]);

  const closeModal = useCallback(() => {
    setSelectedJob(null);
    setJobLoading(false);
  }, []);

  // Close modal on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeModal();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [closeModal]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !pageData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Page Not Found</h1>
          <p className="text-gray-600">This career page doesn&apos;t exist or isn&apos;t published yet.</p>
        </div>
      </div>
    );
  }

  const { config } = pageData;
  const { branding, layout, sections, sieve } = config;
  const heroSection = sections.find(s => s.type === "hero");
  const jobsSection = sections.find(s => s.type === "jobs");
  const headline = heroSection?.config.headline || pageData.page_title || "Join Our Team";
  const subtitle = heroSection?.config.subtitle || pageData.meta_description || "";
  const gradientAngle = layout.gradient_angle ?? 135;
  const heroImageUrl = layout.hero_image_url || "";
  const overlayOpacity = layout.hero_overlay_opacity ?? 40;

  function getHeroStyle(): React.CSSProperties {
    if (layout.hero_style === "image" && heroImageUrl) {
      return { backgroundImage: `url(${heroImageUrl})`, backgroundSize: "cover", backgroundPosition: "center", position: "relative" };
    }
    if (layout.hero_style === "gradient") {
      return { background: `linear-gradient(${gradientAngle}deg, ${branding.colors.primary}, ${branding.colors.secondary})` };
    }
    if (layout.hero_style === "minimal") {
      return { backgroundColor: branding.colors.background, borderBottom: "1px solid #e5e7eb" };
    }
    return { background: `linear-gradient(${gradientAngle}deg, ${branding.colors.primary}, ${branding.colors.secondary})` };
  }

  const isImageHero = layout.hero_style === "image" && heroImageUrl;
  const isMinimalHero = layout.hero_style === "minimal";

  function formatSalary(min: number | null, max: number | null, currency: string | null) {
    if (!min && !max) return null;
    const c = currency || "USD";
    const fmt = (n: number) => n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
    if (min && max) return `${c === "USD" ? "$" : c + " "}${fmt(min)} – ${fmt(max)}`;
    if (min) return `${c === "USD" ? "$" : c + " "}${fmt(min)}+`;
    return `Up to ${c === "USD" ? "$" : c + " "}${fmt(max!)}`;
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: branding.colors.background, fontFamily: branding.fonts?.body || "Inter, sans-serif" }}>
      {/* Navigation Bar */}
      {branding.website_url && (
        <nav className="bg-white border-b">
          <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
            <a href={branding.website_url} className="flex items-center gap-2 text-sm font-medium hover:opacity-80 transition-opacity" style={{ color: branding.colors.primary }}>
              {branding.logo_url ? (
                <img src={branding.logo_url} alt={branding.logo_alt || "Company logo"} className="h-8 object-contain" />
              ) : (
                <span style={{ fontFamily: branding.fonts?.heading || "Inter, sans-serif" }}>Home</span>
              )}
            </a>
            <a
              href={branding.website_url}
              className="text-sm font-medium px-4 py-1.5 rounded-lg border hover:bg-gray-50 transition-colors"
              style={{ color: branding.colors.primary, borderColor: branding.colors.primary }}
            >
              ← Back to Website
            </a>
          </div>
        </nav>
      )}

      {/* Hero */}
      {heroSection?.enabled !== false && (
        <div className="relative" style={getHeroStyle()}>
          {isImageHero && (
            <div className="absolute inset-0" style={{ backgroundColor: `rgba(0,0,0,${overlayOpacity / 100})` }} />
          )}
          <div className={`relative max-w-5xl mx-auto px-4 text-center ${isImageHero ? "py-24" : "py-16"}`}>
            {branding.logo_url && !branding.website_url && (
              <img src={branding.logo_url} alt={branding.logo_alt || ""} className="h-14 mx-auto mb-6 object-contain" />
            )}
            {branding.logo_url && branding.website_url && (
              <a href={branding.website_url} className="inline-block mb-6 hover:opacity-80 transition-opacity">
                <img src={branding.logo_url} alt={branding.logo_alt || ""} className="h-14 mx-auto object-contain" />
              </a>
            )}
            <h1
              className={`text-4xl md:text-5xl font-bold mb-3 ${isMinimalHero ? "" : "text-white"}`}
              style={{ color: isMinimalHero ? branding.colors.text : undefined, fontFamily: branding.fonts?.heading || "Inter, sans-serif" }}
            >
              {headline}
            </h1>
            {subtitle && (
              <p className={`text-lg md:text-xl max-w-2xl mx-auto ${isMinimalHero ? "text-gray-600" : "text-white/85"}`}>
                {subtitle}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Search Bar */}
      <div className="max-w-5xl mx-auto px-4 -mt-6 relative z-10">
        <div className="bg-white rounded-xl shadow-lg p-4 flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Search jobs..."
              className="w-full pl-10 pr-4 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600"
            />
          </div>
          <div className="relative sm:w-52">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={location}
              onChange={e => { setLocation(e.target.value); setPage(1); }}
              placeholder="Location..."
              className="w-full pl-10 pr-4 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600"
            />
          </div>
        </div>
      </div>

      {/* Jobs List */}
      <div className="max-w-5xl mx-auto px-4 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold" style={{ color: branding.colors.text, fontFamily: branding.fonts?.heading || "Inter, sans-serif" }}>
            {jobsSection?.config.title || "Open Positions"}
          </h2>
          <span className="text-sm text-gray-500">{totalJobs} role{totalJobs !== 1 ? "s" : ""}</span>
        </div>

        {jobs.length === 0 ? (
          <div className="bg-white rounded-xl border p-12 text-center">
            <Briefcase className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-700 mb-1">No open positions right now</h3>
            <p className="text-gray-500">Check back soon — we&apos;re always growing.</p>
          </div>
        ) : (
          <div className={`grid gap-4 ${layout.job_display === "grid" ? "sm:grid-cols-2" : ""}`}>
            {jobs.map(job => {
              const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency);
              return (
                <button
                  key={job.id}
                  onClick={() => openJobDetail(job.id)}
                  className="bg-white rounded-xl border p-5 hover:shadow-md transition-shadow text-left w-full group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-lg font-semibold text-gray-900 group-hover:underline">
                        {job.title}
                        {job.job_id_external && (
                          <span className="ml-2 text-sm font-normal text-gray-400">#{job.job_id_external}</span>
                        )}
                      </h3>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-gray-500 mt-1 shrink-0 transition-colors" />
                  </div>

                  {job.company && (
                    <p className="flex items-center gap-1 text-sm text-gray-600 mt-1"><Building2 className="w-3.5 h-3.5" />{job.company}</p>
                  )}

                  <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500 mt-2">
                    {job.location && (
                      <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{job.location}</span>
                    )}
                    {job.location_type && (
                      <span className="capitalize px-2 py-0.5 bg-gray-100 rounded-full text-xs">{job.location_type}</span>
                    )}
                    {salary && layout.show_salary_ranges && (
                      <span className="flex items-center gap-1"><DollarSign className="w-3.5 h-3.5" />{salary}</span>
                    )}
                    {job.application_deadline && (
                      <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" />Deadline: {new Date(job.application_deadline).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalJobs > 12 && (
          <div className="flex justify-center gap-2 mt-8">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <span className="px-4 py-2 text-sm text-gray-600">Page {page}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={jobs.length < 12}
              className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Job Detail Modal */}
      {(selectedJob || jobLoading) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={closeModal}>
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/50" />

          {/* Modal */}
          <div
            className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {jobLoading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 className="w-8 h-8 animate-spin" style={{ color: branding.colors.primary }} />
              </div>
            ) : selectedJob ? (
              <>
                {/* Modal Header */}
                <div className="p-6 pb-4 border-b shrink-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h2 className="text-2xl font-bold text-gray-900" style={{ fontFamily: branding.fonts?.heading || "Inter, sans-serif" }}>
                        {selectedJob.title}
                        {selectedJob.job_id_external && (
                          <span className="ml-2 text-base font-normal text-gray-400">#{selectedJob.job_id_external}</span>
                        )}
                      </h2>
                      {selectedJob.company && (
                        <p className="flex items-center gap-1.5 text-base text-gray-600 mt-1">
                          <Building2 className="w-4 h-4 shrink-0" />{selectedJob.company}
                        </p>
                      )}
                    </div>
                    <button onClick={closeModal} className="p-2 hover:bg-gray-100 rounded-lg transition-colors shrink-0" aria-label="Close">
                      <X className="w-5 h-5 text-gray-500" />
                    </button>
                  </div>

                  {/* Meta tags */}
                  <div className="flex flex-wrap items-center gap-3 mt-4 text-sm text-gray-600">
                    {selectedJob.location && (
                      <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 rounded-full">
                        <MapPin className="w-3.5 h-3.5" />{selectedJob.location}
                      </span>
                    )}
                    {selectedJob.location_type && (
                      <span className="capitalize px-3 py-1.5 bg-gray-100 rounded-full">
                        {selectedJob.location_type}
                      </span>
                    )}
                    {(() => {
                      const sal = formatSalary(selectedJob.salary_min, selectedJob.salary_max, selectedJob.salary_currency);
                      return sal && layout.show_salary_ranges ? (
                        <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 rounded-full">
                          <DollarSign className="w-3.5 h-3.5" />{sal}
                        </span>
                      ) : null;
                    })()}
                    {selectedJob.application_deadline && (
                      <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 rounded-full">
                        <Calendar className="w-3.5 h-3.5" />Deadline: {new Date(selectedJob.application_deadline).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </span>
                    )}
                    {selectedJob.posted_at && (
                      <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 rounded-full">
                        <Clock className="w-3.5 h-3.5" />Posted: {new Date(selectedJob.posted_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </span>
                    )}
                  </div>
                </div>

                {/* Modal Body — Scrollable */}
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="prose prose-sm max-w-none text-gray-700 prose-headings:text-gray-900 prose-headings:mt-6 prose-headings:mb-2 prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5">
                    {selectedJob.description_html ? (
                      <div dangerouslySetInnerHTML={{ __html: selectedJob.description_html }} />
                    ) : (
                      <div className="space-y-3">
                        {selectedJob.description_text.split(/\n\s*\n/).map((para, i) => (
                          <p key={i} className="leading-relaxed whitespace-pre-wrap">{para.trim()}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Modal Footer — Apply Button */}
                <div className="p-6 pt-4 border-t shrink-0 flex items-center gap-3">
                  {selectedJob.url ? (
                    <a
                      href={selectedJob.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 flex items-center justify-center gap-2 text-center font-medium py-3 rounded-lg transition-colors text-white"
                      style={{ backgroundColor: branding.colors.primary }}
                    >
                      Apply Now <ExternalLink className="w-4 h-4" />
                    </a>
                  ) : (
                    <span className="flex-1 text-center font-medium py-3 rounded-lg text-white" style={{ backgroundColor: branding.colors.primary }}>
                      Apply Now
                    </span>
                  )}
                  <button
                    onClick={closeModal}
                    className="px-6 py-3 border rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* Sieve Chat Bubble */}
      {sieve?.enabled && (
        <div className="fixed bottom-6 right-6 z-50">
          <button className="w-14 h-14 rounded-full shadow-lg flex items-center justify-center hover:scale-105 transition-transform"
            style={{ backgroundColor: branding.colors.primary }}
            title={`Chat with ${sieve.name || "Sieve"}`}
          >
            <MessageSquare className="w-6 h-6 text-white" />
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t py-6 text-center text-sm text-gray-400">
        Powered by <a href="https://winnowcc.ai" className="text-gray-500 hover:underline">Winnow Career Concierge</a>
      </footer>
    </div>
  );
}
