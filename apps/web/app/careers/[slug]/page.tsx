"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { MapPin, DollarSign, Loader2, Briefcase, Search, MessageSquare } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface CareerPageData {
  slug: string;
  page_title: string | null;
  meta_description: string | null;
  config: {
    branding: {
      colors: Record<string, string>;
      logo_url?: string;
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
  location: string | null;
  location_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  posted_at: string;
}

export default function PublicCareerPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [pageData, setPageData] = useState<CareerPageData | null>(null);
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetch(`${API}/api/public/career-pages/${slug}`)
      .then(res => { if (!res.ok) throw new Error(); return res.json(); })
      .then(setPageData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    if (!pageData) return;
    const params = new URLSearchParams({ page: String(page), page_size: "12" });
    if (search) params.set("search", search);
    if (location) params.set("location", location);

    fetch(`${API}/api/public/career-pages/${slug}/jobs?${params}`)
      .then(res => res.ok ? res.json() : { jobs: [], total: 0 })
      .then(data => { setJobs(data.jobs); setTotalJobs(data.total); });
  }, [slug, pageData, page, search, location]);

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
      {/* Hero */}
      {heroSection?.enabled !== false && (
        <div className="relative" style={getHeroStyle()}>
          {isImageHero && (
            <div className="absolute inset-0" style={{ backgroundColor: `rgba(0,0,0,${overlayOpacity / 100})` }} />
          )}
          <div className={`relative max-w-5xl mx-auto px-4 text-center ${isImageHero ? "py-24" : "py-16"}`}>
            {branding.logo_url && (
              <img src={branding.logo_url} alt="" className="h-14 mx-auto mb-6 object-contain" />
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
                <div key={job.id} className="bg-white rounded-xl border p-5 hover:shadow-md transition-shadow">
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">{job.title}</h3>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500 mb-4">
                    {job.location && (
                      <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{job.location}</span>
                    )}
                    {job.location_type && (
                      <span className="capitalize px-2 py-0.5 bg-gray-100 rounded-full text-xs">{job.location_type}</span>
                    )}
                    {salary && layout.show_salary_ranges && (
                      <span className="flex items-center gap-1"><DollarSign className="w-3.5 h-3.5" />{salary}</span>
                    )}
                  </div>
                  <Link
                    href={`/careers/${slug}/jobs/${job.id}/apply`}
                    className="inline-block w-full text-center text-sm font-medium py-2.5 rounded-lg transition-colors"
                    style={{ backgroundColor: branding.colors.accent, color: branding.colors.primary }}
                  >
                    Apply Now
                  </Link>
                </div>
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
        Powered by <a href="https://winnowcc.ai" className="text-gray-500 hover:underline">Winnow</a>
      </footer>
    </div>
  );
}
