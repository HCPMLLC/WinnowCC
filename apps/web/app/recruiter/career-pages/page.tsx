"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, Globe, Eye, Edit, Trash2, ExternalLink, Copy, Check, Settings } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface CareerPage {
  id: string;
  name: string;
  slug: string;
  published: boolean;
  public_url: string;
  view_count: number;
  application_count: number;
}

export default function CareerPagesPage() {
  const [pages, setPages] = useState<CareerPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/career-pages`, { credentials: "include" })
      .then(res => res.ok ? res.json() : { pages: [] })
      .then(data => setPages(data.pages))
      .finally(() => setLoading(false));
  }, []);

  async function copyEmbedCode(page: CareerPage) {
    const code = `<div id="winnow-jobs" data-slug="${page.slug}"></div>\n<script src="https://api.winnowcc.ai/embed/winnow-widget.js" async></script>`;
    await navigator.clipboard.writeText(code);
    setCopiedId(page.id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  async function deletePage(id: string) {
    if (!confirm("Delete this career page?")) return;
    const res = await fetch(`${API}/api/career-pages/${id}`, { method: "DELETE", credentials: "include" });
    if (res.ok) setPages(pages.filter(p => p.id !== id));
  }

  if (loading) return <div className="flex justify-center p-12"><div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full" /></div>;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Career Pages</h1>
          <p className="text-gray-600 mt-1">Branded pages to showcase your open positions</p>
        </div>
        <Link href="/recruiter/career-pages/new" className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
          <Plus className="w-5 h-5" /> Create Career Page
        </Link>
      </div>

      {pages.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center">
          <Globe className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No career pages yet</h3>
          <p className="text-gray-600 mb-6">Create a branded career page with Sieve AI-powered applications.</p>
          <Link href="/recruiter/career-pages/new" className="inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700">
            <Plus className="w-5 h-5" /> Create Your First Page
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {pages.map(page => (
            <div key={page.id} className="bg-white rounded-xl border p-6 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-semibold">{page.name}</h3>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${page.published ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>
                      {page.published ? "Published" : "Draft"}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <a href={page.public_url} target="_blank" className="flex items-center gap-1 hover:text-blue-600">
                      <Globe className="w-4 h-4" /> winnowcc.ai/careers/{page.slug} <ExternalLink className="w-3 h-3" />
                    </a>
                    <span className="flex items-center gap-1"><Eye className="w-4 h-4" /> {page.view_count} views</span>
                    <Link href={`/recruiter/career-pages/${page.id}/applications`} className="hover:text-blue-600">{page.application_count} applications</Link>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => copyEmbedCode(page)} className="p-2 hover:bg-gray-100 rounded-lg" title="Copy embed code">
                    {copiedId === page.id ? <Check className="w-5 h-5 text-green-600" /> : <Copy className="w-5 h-5 text-gray-500" />}
                  </button>
                  <Link href={`/recruiter/career-pages/${page.id}/builder`} className="p-2 hover:bg-gray-100 rounded-lg"><Edit className="w-5 h-5 text-gray-500" /></Link>
                  <Link href={`/recruiter/career-pages/${page.id}`} className="p-2 hover:bg-gray-100 rounded-lg"><Settings className="w-5 h-5 text-gray-500" /></Link>
                  <button onClick={() => deletePage(page.id)} className="p-2 hover:bg-red-50 rounded-lg"><Trash2 className="w-5 h-5 text-gray-500 hover:text-red-600" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
