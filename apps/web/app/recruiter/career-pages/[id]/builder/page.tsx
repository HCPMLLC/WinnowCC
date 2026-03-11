"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Eye, Save, Globe, Loader2, Check, Palette, Layout, Layers, MessageSquare, Image, Type, Building2, Calendar, Download } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface CareerPageConfig {
  branding: { colors: Record<string, string>; logo_url?: string; fonts: { heading: string; body: string } };
  layout: {
    hero_style: string; gradient_angle?: number; hero_image_url?: string; hero_overlay_opacity?: number;
    job_display: string; show_ips_preview: boolean; show_salary_ranges: boolean;
  };
  sections: Array<{ type: string; enabled: boolean; config: Record<string, any> }>;
  sieve: { enabled: boolean; name: string; welcome_message: string; tone: string };
}

interface CareerPage {
  id: string;
  name: string;
  slug: string;
  published: boolean;
  public_url: string;
  config: CareerPageConfig;
}

type Tab = "branding" | "layout" | "sections" | "sieve";

export default function CareerPageBuilderPage() {
  const params = useParams();
  const pageId = params.id as string;
  const [page, setPage] = useState<CareerPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("branding");

  useEffect(() => {
    fetch(`${API}/api/career-pages/${pageId}`, { credentials: "include" })
      .then(res => res.ok ? res.json() : null)
      .then(setPage)
      .finally(() => setLoading(false));
  }, [pageId]);

  const updateConfig = useCallback((updates: Partial<CareerPageConfig>) => {
    if (!page) return;
    setPage({ ...page, config: { ...page.config, ...updates } });
    setSaved(false);
  }, [page]);

  async function savePage() {
    if (!page) return;
    setSaving(true);
    const res = await fetch(`${API}/api/career-pages/${pageId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ config: page.config }),
    });
    if (res.ok) { setSaved(true); setTimeout(() => setSaved(false), 2000); }
    setSaving(false);
  }

  async function publishPage() {
    if (!page) return;
    setSaving(true);
    const res = await fetch(`${API}/api/career-pages/${pageId}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ publish: !page.published }),
    });
    if (res.ok) setPage(await res.json());
    setSaving(false);
  }

  if (loading) return <div className="flex justify-center items-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>;
  if (!page) return <div className="flex justify-center items-center min-h-screen text-gray-600">Not found</div>;

  const tabs = [
    { id: "branding" as Tab, label: "Branding", icon: <Palette className="w-4 h-4" /> },
    { id: "layout" as Tab, label: "Layout", icon: <Layout className="w-4 h-4" /> },
    { id: "sections" as Tab, label: "Content", icon: <Type className="w-4 h-4" /> },
    { id: "sieve" as Tab, label: "Sieve AI", icon: <MessageSquare className="w-4 h-4" /> },
  ];

  const heroSection = page.config.sections.find(s => s.type === "hero");
  const jobsSection = page.config.sections.find(s => s.type === "jobs");
  const headline = heroSection?.config.headline || "Join Our Team";
  const subtitle = heroSection?.config.subtitle || "";
  const gradientAngle = page.config.layout.gradient_angle ?? 135;
  const heroImageUrl = page.config.layout.hero_image_url || "";
  const overlayOpacity = page.config.layout.hero_overlay_opacity ?? 40;

  function getHeroStyle(): React.CSSProperties {
    const { hero_style } = page!.config.layout;
    const { primary, secondary } = page!.config.branding.colors;
    if (hero_style === "image" && heroImageUrl) {
      return {
        backgroundImage: `url(${heroImageUrl})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
        position: "relative",
      };
    }
    if (hero_style === "gradient") {
      return { background: `linear-gradient(${gradientAngle}deg, ${primary}, ${secondary})` };
    }
    if (hero_style === "minimal") {
      return { backgroundColor: page!.config.branding.colors.background, borderBottom: "1px solid #e5e7eb" };
    }
    return { background: `linear-gradient(${gradientAngle}deg, ${primary}, ${secondary})` };
  }

  const isImageHero = page.config.layout.hero_style === "image" && heroImageUrl;
  const isMinimalHero = page.config.layout.hero_style === "minimal";

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/recruiter/career-pages" className="p-2 hover:bg-gray-100 rounded-lg"><ArrowLeft className="w-5 h-5 text-gray-600" /></Link>
          <div>
            <h1 className="font-semibold">{page.name}</h1>
            <p className="text-sm text-gray-500">Career Page Builder</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <a href={`${page.public_url}?preview=true`} target="_blank" className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg">
            <Eye className="w-4 h-4" /> Preview
          </a>
          <button onClick={savePage} disabled={saving || saved} className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50 disabled:opacity-50">
            {saved ? <><Check className="w-4 h-4 text-green-600" /> Saved</> : saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</> : <><Save className="w-4 h-4" /> Save</>}
          </button>
          <button onClick={publishPage} disabled={saving} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${page.published ? "bg-gray-100 text-gray-700" : "bg-blue-600 text-white"}`}>
            <Globe className="w-4 h-4" /> {page.published ? "Unpublish" : "Publish"}
          </button>
        </div>
      </header>

      <div className="flex">
        <aside className="w-80 bg-white border-r min-h-[calc(100vh-65px)] overflow-y-auto">
          <nav className="p-4 border-b">
            {tabs.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg mb-1 ${activeTab === tab.id ? "bg-blue-100 text-blue-600" : "text-gray-700 hover:bg-gray-100"}`}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </nav>
          <div className="p-4">
            {activeTab === "branding" && <BrandingPanel config={page.config.branding} onChange={branding => updateConfig({ branding })} onImportBranding={async (url) => {
              const res = await fetch(`${API}/api/career-pages/${pageId}/import-branding`, {
                method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
                body: JSON.stringify({ website_url: url }),
              });
              if (!res.ok) throw new Error("Failed to import");
              const kit = await res.json();
              const newBranding = { ...page.config.branding, colors: kit.colors, fonts: kit.fonts, ...(kit.logo_url ? { logo_url: kit.logo_url } : {}) };
              const newLayout = { ...page.config.layout, ...(kit.hero_image_url ? { hero_image_url: kit.hero_image_url, hero_style: "image" } : {}) };
              updateConfig({ branding: newBranding, layout: newLayout });
            }} />}
            {activeTab === "layout" && <LayoutPanel config={page.config.layout} onChange={layout => updateConfig({ layout })} />}
            {activeTab === "sections" && (
              <SectionsPanel
                sections={page.config.sections}
                onChange={sections => updateConfig({ sections })}
              />
            )}
            {activeTab === "sieve" && <SievePanel config={page.config.sieve} onChange={sieve => updateConfig({ sieve })} />}
          </div>
        </aside>

        {/* Live Preview */}
        <main className="flex-1 p-8">
          <div className="bg-white rounded-xl shadow-lg overflow-hidden max-w-4xl mx-auto min-h-[600px]" style={{ backgroundColor: page.config.branding.colors.background }}>
            {/* Hero */}
            {heroSection?.enabled !== false && (
              <div className="relative" style={getHeroStyle()}>
                {isImageHero && (
                  <div className="absolute inset-0" style={{ backgroundColor: `rgba(0,0,0,${overlayOpacity / 100})` }} />
                )}
                <div className={`relative p-12 text-center ${isImageHero ? "py-20" : "py-12"}`}>
                  {page.config.branding.logo_url && (
                    <img src={page.config.branding.logo_url} alt="Logo" className="h-12 mx-auto mb-4 object-contain" />
                  )}
                  <h2 className={`text-3xl font-bold mb-2 ${isMinimalHero ? "" : "text-white"}`} style={isMinimalHero ? { color: page.config.branding.colors.text } : undefined}>
                    {headline}
                  </h2>
                  {subtitle && (
                    <p className={`text-lg ${isMinimalHero ? "text-gray-600" : "text-white/80"}`}>
                      {subtitle}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Jobs Section */}
            <div className="p-8">
              <h3 className="text-xl font-semibold mb-4" style={{ color: page.config.branding.colors.text }}>
                {jobsSection?.config.title || "Open Positions"}
              </h3>
              <div className={`grid ${page.config.layout.job_display === "grid" ? "grid-cols-2" : ""} gap-4`}>
                {[
                  { title: "Senior Software Engineer", company: "Acme Corp", loc: "Remote", sal: "$130k – $170k", deadline: "Apr 15, 2026" },
                  { title: "Product Designer", company: "TechStart Inc", loc: "New York, NY", sal: "$110k – $140k", deadline: "Apr 20, 2026" },
                  { title: "Marketing Manager", company: "GrowthCo", loc: "Remote", sal: "$95k – $125k", deadline: "May 1, 2026" },
                ].map((job, i) => (
                  <div key={i} className="border rounded-lg p-4 hover:shadow-md transition-shadow group">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-medium text-gray-900">{job.title}</h4>
                        <p className="flex items-center gap-1 text-sm text-gray-600"><Building2 className="w-3.5 h-3.5" />{job.company}</p>
                        <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500 mt-1">
                          <span>{job.loc}</span>
                          {page.config.layout.show_salary_ranges && <span>· {job.sal}</span>}
                        </div>
                        <p className="flex items-center gap-1 text-xs text-gray-400 mt-1"><Calendar className="w-3 h-3" />Deadline: {job.deadline}</p>
                      </div>
                      {page.config.layout.show_ips_preview && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full whitespace-nowrap">{85 + i * 3}% Match</span>
                      )}
                    </div>
                    <button className="mt-3 w-full text-sm font-medium py-2 rounded-lg transition-colors"
                      style={{ backgroundColor: page.config.branding.colors.accent, color: page.config.branding.colors.primary }}>
                      Apply Now
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Sieve Chat Bubble Preview */}
            {page.config.sieve.enabled && (
              <div className="fixed bottom-6 right-6 pointer-events-none z-10">
                <div className="w-14 h-14 rounded-full shadow-lg flex items-center justify-center" style={{ backgroundColor: page.config.branding.colors.primary }}>
                  <MessageSquare className="w-6 h-6 text-white" />
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

/* ────────────────────── Panel Components ────────────────────── */

function BrandingPanel({ config, onChange, onImportBranding }: { config: any; onChange: (c: any) => void; onImportBranding?: (url: string) => Promise<void> }) {
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState(false);

  async function handleImport() {
    if (!importUrl || !onImportBranding) return;
    setImporting(true);
    setImportError(null);
    setImportSuccess(false);
    try {
      await onImportBranding(importUrl);
      setImportSuccess(true);
      setTimeout(() => setImportSuccess(false), 3000);
    } catch {
      setImportError("Could not extract branding. Check the URL and try again.");
    }
    setImporting(false);
  }

  return (
    <div className="space-y-6">
      {/* Import from Website */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h3 className="font-medium mb-1 text-blue-900">Import from Website</h3>
        <p className="text-xs text-blue-700 mb-3">Auto-extract colors, fonts, logo, and hero image from your website</p>
        <div className="flex gap-2">
          <input
            type="url"
            value={importUrl}
            onChange={e => setImportUrl(e.target.value)}
            placeholder="https://yourcompany.com"
            className="flex-1 px-3 py-2 border rounded-lg text-sm bg-white"
            onKeyDown={e => e.key === "Enter" && handleImport()}
          />
          <button
            onClick={handleImport}
            disabled={importing || !importUrl}
            className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap"
          >
            {importing ? <><Loader2 className="w-4 h-4 animate-spin" /> Scanning...</> : importSuccess ? <><Check className="w-4 h-4" /> Imported!</> : <><Download className="w-4 h-4" /> Import</>}
          </button>
        </div>
        {importError && <p className="text-xs text-red-600 mt-2">{importError}</p>}
        {importSuccess && <p className="text-xs text-green-600 mt-2">Branding imported! Review below and click Save.</p>}
      </div>

      <div>
        <h3 className="font-medium mb-4">Colors</h3>
        {Object.entries(config.colors).map(([key, value]) => (
          <div key={key} className="flex items-center gap-3 mb-2">
            <input type="color" value={value as string} onChange={e => onChange({ ...config, colors: { ...config.colors, [key]: e.target.value } })} className="w-10 h-10 rounded cursor-pointer border" />
            <span className="text-sm capitalize">{key}</span>
          </div>
        ))}
      </div>
      <div>
        <h3 className="font-medium mb-2">Logo URL</h3>
        <input type="url" value={config.logo_url || ""} onChange={e => onChange({ ...config, logo_url: e.target.value })} placeholder="https://your-logo.png" className="w-full px-3 py-2 border rounded-lg text-sm" />
        {config.logo_url && (
          <div className="mt-2 p-3 border rounded-lg bg-gray-50 flex items-center justify-center">
            <img src={config.logo_url} alt="Preview" className="h-10 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          </div>
        )}
      </div>
      <div>
        <h3 className="font-medium mb-2">Heading Font</h3>
        <select value={config.fonts?.heading || "Inter"} onChange={e => onChange({ ...config, fonts: { ...config.fonts, heading: e.target.value } })} className="w-full px-3 py-2 border rounded-lg text-sm">
          {["Inter", "Poppins", "Roboto", "Open Sans", "Montserrat", "Playfair Display", "Lora", "DM Sans", "Lato"].map(f => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>
      <div>
        <h3 className="font-medium mb-2">Body Font</h3>
        <select value={config.fonts?.body || "Inter"} onChange={e => onChange({ ...config, fonts: { ...config.fonts, body: e.target.value } })} className="w-full px-3 py-2 border rounded-lg text-sm">
          {["Inter", "Roboto", "Open Sans", "Lato", "Source Sans Pro", "DM Sans", "Nunito"].map(f => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

function LayoutPanel({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-6">
      {/* Hero Style */}
      <div>
        <h3 className="font-medium mb-3">Hero Style</h3>
        <div className="grid grid-cols-2 gap-2">
          {["gradient", "image", "minimal"].map(s => (
            <button key={s} onClick={() => onChange({ ...config, hero_style: s })} className={`px-3 py-2 text-sm rounded-lg border capitalize ${config.hero_style === s ? "border-blue-600 bg-blue-100 text-blue-600" : "hover:bg-gray-50"}`}>{s}</button>
          ))}
        </div>
      </div>

      {/* Gradient Controls */}
      {config.hero_style === "gradient" && (
        <div>
          <h3 className="font-medium mb-2">Gradient Angle</h3>
          <div className="flex items-center gap-3">
            <input type="range" min="0" max="360" value={config.gradient_angle ?? 135}
              onChange={e => onChange({ ...config, gradient_angle: parseInt(e.target.value) })}
              className="flex-1 accent-blue-600" />
            <span className="text-sm text-gray-600 w-10 text-right">{config.gradient_angle ?? 135}°</span>
          </div>
          <div className="mt-2 h-8 rounded-lg" style={{ background: `linear-gradient(${config.gradient_angle ?? 135}deg, var(--preview-primary, #1B3025), var(--preview-secondary, #E8C84A))` }} />
        </div>
      )}

      {/* Hero Image */}
      {config.hero_style === "image" && (
        <div className="space-y-4">
          <div>
            <h3 className="font-medium mb-2">Hero Image URL</h3>
            <div className="flex items-center gap-2">
              <Image className="w-4 h-4 text-gray-400 shrink-0" />
              <input type="url" value={config.hero_image_url || ""} onChange={e => onChange({ ...config, hero_image_url: e.target.value })} placeholder="https://your-hero-image.jpg" className="flex-1 px-3 py-2 border rounded-lg text-sm" />
            </div>
            {config.hero_image_url && (
              <div className="mt-2 rounded-lg overflow-hidden border h-24">
                <img src={config.hero_image_url} alt="Hero preview" className="w-full h-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
              </div>
            )}
          </div>
          <div>
            <h3 className="font-medium mb-2">Overlay Darkness</h3>
            <div className="flex items-center gap-3">
              <input type="range" min="0" max="80" value={config.hero_overlay_opacity ?? 40}
                onChange={e => onChange({ ...config, hero_overlay_opacity: parseInt(e.target.value) })}
                className="flex-1 accent-blue-600" />
              <span className="text-sm text-gray-600 w-10 text-right">{config.hero_overlay_opacity ?? 40}%</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">Controls how dark the overlay is so text stays readable</p>
          </div>
        </div>
      )}

      {/* Job Display */}
      <div>
        <h3 className="font-medium mb-3">Job Card Layout</h3>
        <div className="grid grid-cols-3 gap-2">
          {["grid", "list", "compact"].map(d => (
            <button key={d} onClick={() => onChange({ ...config, job_display: d })} className={`px-3 py-2 text-sm rounded-lg border capitalize ${config.job_display === d ? "border-blue-600 bg-blue-100 text-blue-600" : "hover:bg-gray-50"}`}>{d}</button>
          ))}
        </div>
      </div>

      {/* Toggles */}
      <div className="space-y-3">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={config.show_ips_preview} onChange={e => onChange({ ...config, show_ips_preview: e.target.checked })} className="rounded" />
          <span className="text-sm">Show Match Score</span>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={config.show_salary_ranges} onChange={e => onChange({ ...config, show_salary_ranges: e.target.checked })} className="rounded" />
          <span className="text-sm">Show Salary Ranges</span>
        </label>
      </div>
    </div>
  );
}

function SectionsPanel({ sections, onChange }: { sections: any[]; onChange: (s: any[]) => void }) {
  function updateSectionConfig(type: string, updates: Record<string, any>) {
    onChange(sections.map(s => s.type === type ? { ...s, config: { ...s.config, ...updates } } : s));
  }

  function toggleSection(type: string) {
    onChange(sections.map(s => s.type === type ? { ...s, enabled: !s.enabled } : s));
  }

  const heroSection = sections.find(s => s.type === "hero");
  const jobsSection = sections.find(s => s.type === "jobs");

  return (
    <div className="space-y-6">
      {/* Hero Content */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium">Hero Section</h3>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={heroSection?.enabled !== false} onChange={() => toggleSection("hero")} className="rounded" />
            <span className="text-xs text-gray-500">Show</span>
          </label>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Headline</label>
            <input type="text" value={heroSection?.config.headline || ""} onChange={e => updateSectionConfig("hero", { headline: e.target.value })} placeholder="Join Our Team" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Subtitle</label>
            <input type="text" value={heroSection?.config.subtitle || ""} onChange={e => updateSectionConfig("hero", { subtitle: e.target.value })} placeholder="Build the future with us" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
        </div>
      </div>

      <hr />

      {/* Jobs Section */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium">Jobs Section</h3>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={jobsSection?.enabled !== false} onChange={() => toggleSection("jobs")} className="rounded" />
            <span className="text-xs text-gray-500">Show</span>
          </label>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Section Title</label>
          <input type="text" value={jobsSection?.config.title || ""} onChange={e => updateSectionConfig("jobs", { title: e.target.value })} placeholder="Open Positions" className="w-full px-3 py-2 border rounded-lg text-sm" />
        </div>
      </div>

      <hr />

      {/* Other sections */}
      <div>
        <h3 className="font-medium mb-3">Additional Sections</h3>
        {sections.filter(s => s.type !== "hero" && s.type !== "jobs").map(section => (
          <label key={section.type} className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 mb-2">
            <input type="checkbox" checked={section.enabled} onChange={() => toggleSection(section.type)} className="rounded" />
            <span className="text-sm capitalize">{section.type}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function SievePanel({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-6">
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={config.enabled} onChange={e => onChange({ ...config, enabled: e.target.checked })} className="rounded" />
        <span className="font-medium">Enable Sieve AI Chat</span>
      </label>
      <p className="text-xs text-gray-500 -mt-4">Sieve guides applicants through the application conversationally</p>
      <div>
        <label className="block text-sm font-medium mb-2">Assistant Name</label>
        <input type="text" value={config.name} onChange={e => onChange({ ...config, name: e.target.value })} className="w-full px-3 py-2 border rounded-lg text-sm" />
      </div>
      <div>
        <label className="block text-sm font-medium mb-2">Welcome Message</label>
        <textarea value={config.welcome_message} onChange={e => onChange({ ...config, welcome_message: e.target.value })} rows={3} className="w-full px-3 py-2 border rounded-lg text-sm" />
      </div>
      <div>
        <label className="block text-sm font-medium mb-2">Tone</label>
        <select value={config.tone} onChange={e => onChange({ ...config, tone: e.target.value })} className="w-full px-3 py-2 border rounded-lg text-sm">
          <option value="professional">Professional</option>
          <option value="casual">Casual</option>
          <option value="enthusiastic">Enthusiastic</option>
        </select>
      </div>
    </div>
  );
}
