"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Eye, Save, Globe, Loader2, Check, Palette, Layout, Layers, MessageSquare } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface CareerPageConfig {
  branding: { colors: Record<string, string>; logo_url?: string; fonts: { heading: string; body: string } };
  layout: { hero_style: string; job_display: string; show_ips_preview: boolean; show_salary_ranges: boolean };
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
    { id: "sections" as Tab, label: "Sections", icon: <Layers className="w-4 h-4" /> },
    { id: "sieve" as Tab, label: "Sieve AI", icon: <MessageSquare className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/employer/career-pages" className="p-2 hover:bg-gray-100 rounded-lg"><ArrowLeft className="w-5 h-5 text-gray-600" /></Link>
          <div>
            <h1 className="font-semibold">{page.name}</h1>
            <p className="text-sm text-gray-500">Career Page Builder</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <a href={page.public_url} target="_blank" className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg">
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
        {/* Sidebar */}
        <aside className="w-80 bg-white border-r min-h-[calc(100vh-65px)]">
          <nav className="p-4 border-b">
            {tabs.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg mb-1 ${activeTab === tab.id ? "bg-blue-100 text-blue-600" : "text-gray-700 hover:bg-gray-100"}`}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </nav>
          <div className="p-4">
            {activeTab === "branding" && <BrandingPanel config={page.config.branding} onChange={branding => updateConfig({ branding })} />}
            {activeTab === "layout" && <LayoutPanel config={page.config.layout} onChange={layout => updateConfig({ layout })} />}
            {activeTab === "sections" && <SectionsPanel sections={page.config.sections} onChange={sections => updateConfig({ sections })} />}
            {activeTab === "sieve" && <SievePanel config={page.config.sieve} onChange={sieve => updateConfig({ sieve })} />}
          </div>
        </aside>

        {/* Preview */}
        <main className="flex-1 p-8">
          <div className="bg-white rounded-xl shadow-lg overflow-hidden max-w-4xl mx-auto min-h-[600px]" style={{ backgroundColor: page.config.branding.colors.background }}>
            <div className="p-8 text-center" style={{ background: `linear-gradient(135deg, ${page.config.branding.colors.primary}, ${page.config.branding.colors.secondary})` }}>
              <h2 className="text-3xl font-bold text-white mb-2">
                {page.config.sections.find(s => s.type === "hero")?.config.headline || "Join Our Team"}
              </h2>
              <p className="text-white/80">Preview of your career page</p>
            </div>
            <div className="p-8">
              <h3 className="text-xl font-semibold mb-4" style={{ color: page.config.branding.colors.text }}>Open Positions</h3>
              <div className={`grid ${page.config.layout.job_display === "grid" ? "grid-cols-2" : ""} gap-4`}>
                {[1, 2, 3].map(i => (
                  <div key={i} className="border rounded-lg p-4">
                    <h4 className="font-medium">Sample Job Title {i}</h4>
                    <p className="text-sm text-gray-500">Remote - Engineering</p>
                    {page.config.layout.show_salary_ranges && <p className="text-sm text-gray-500">$100k - $150k</p>}
                    {page.config.layout.show_ips_preview && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded mt-2 inline-block">85% Match</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

// Panel components
function BrandingPanel({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-6">
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
        <input type="url" value={config.logo_url || ""} onChange={e => onChange({ ...config, logo_url: e.target.value })} placeholder="https://..." className="w-full px-3 py-2 border rounded-lg text-sm" />
      </div>
    </div>
  );
}

function LayoutPanel({ config, onChange }: { config: any; onChange: (c: any) => void }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium mb-3">Hero Style</h3>
        <div className="grid grid-cols-2 gap-2">
          {["image", "video", "gradient", "minimal"].map(s => (
            <button key={s} onClick={() => onChange({ ...config, hero_style: s })} className={`px-3 py-2 text-sm rounded-lg border capitalize ${config.hero_style === s ? "border-blue-600 bg-blue-100 text-blue-600" : "hover:bg-gray-50"}`}>{s}</button>
          ))}
        </div>
      </div>
      <div>
        <h3 className="font-medium mb-3">Job Display</h3>
        <div className="grid grid-cols-3 gap-2">
          {["grid", "list", "compact"].map(d => (
            <button key={d} onClick={() => onChange({ ...config, job_display: d })} className={`px-3 py-2 text-sm rounded-lg border capitalize ${config.job_display === d ? "border-blue-600 bg-blue-100 text-blue-600" : "hover:bg-gray-50"}`}>{d}</button>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={config.show_ips_preview} onChange={e => onChange({ ...config, show_ips_preview: e.target.checked })} className="rounded" />
          <span className="text-sm">Show IPS Preview</span>
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
  const toggleSection = (type: string) => {
    onChange(sections.map(s => s.type === type ? { ...s, enabled: !s.enabled } : s));
  };
  return (
    <div className="space-y-3">
      <h3 className="font-medium mb-4">Page Sections</h3>
      {sections.map(section => (
        <label key={section.type} className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
          <input type="checkbox" checked={section.enabled} onChange={() => toggleSection(section.type)} className="rounded" />
          <span className="text-sm capitalize">{section.type}</span>
        </label>
      ))}
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
