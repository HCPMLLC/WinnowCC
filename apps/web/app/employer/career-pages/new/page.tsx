"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export default function NewCareerPagePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", slug: "", page_title: "", meta_description: "" });

  function handleNameChange(name: string) {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50);
    setForm({ ...form, name, slug });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const res = await fetch(`${API}/api/career-pages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        ...form,
        config: {
          branding: { colors: { primary: "#1B3025", secondary: "#E8C84A", accent: "#CEE3D8", background: "#FFFFFF", text: "#1B3025" } },
          layout: { hero_style: "gradient", job_display: "grid", show_ips_preview: true, show_salary_ranges: true },
          sections: [
            { type: "hero", enabled: true, config: { headline: "Join Our Team" } },
            { type: "jobs", enabled: true, config: { title: "Open Positions" } },
          ],
          sieve: { enabled: true, name: "Sieve", welcome_message: "Hi! I'm here to help you find your perfect role.", tone: "professional" },
        },
      }),
    });

    if (res.ok) {
      const data = await res.json();
      router.push(`/employer/career-pages/${data.id}/builder`);
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to create");
    }
    setLoading(false);
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <Link href="/employer/career-pages" className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>

      <div className="bg-white rounded-xl border p-8">
        <h1 className="text-2xl font-bold mb-2">Create Career Page</h1>
        <p className="text-gray-600 mb-8">Set up basics, then customize in the visual builder.</p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2">Page Name *</label>
            <input type="text" value={form.name} onChange={e => handleNameChange(e.target.value)} placeholder="Acme Corp Careers" className="w-full px-4 py-2 border rounded-lg" required />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">URL Slug *</label>
            <div className="flex">
              <span className="px-4 py-2 bg-gray-100 border border-r-0 rounded-l-lg text-gray-500 text-sm">careers.winnowcc.ai/</span>
              <input type="text" value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} className="flex-1 px-4 py-2 border rounded-r-lg" required pattern="[a-z0-9-]+" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Page Title</label>
            <input type="text" value={form.page_title} onChange={e => setForm({ ...form, page_title: e.target.value })} placeholder="Careers at Acme Corp" className="w-full px-4 py-2 border rounded-lg" />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Meta Description</label>
            <textarea value={form.meta_description} onChange={e => setForm({ ...form, meta_description: e.target.value })} placeholder="Join our team..." rows={3} className="w-full px-4 py-2 border rounded-lg" />
          </div>

          {error && <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}

          <div className="flex gap-4 pt-4">
            <button type="submit" disabled={loading} className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 flex items-center justify-center gap-2 disabled:opacity-50">
              {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Creating...</> : "Create & Open Builder"}
            </button>
            <Link href="/employer/career-pages" className="px-6 py-3 border rounded-lg text-gray-700 hover:bg-gray-50">Cancel</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
