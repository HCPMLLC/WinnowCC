"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

/**
 * Custom domain resolver page.
 * When a custom domain (e.g., jobs.hcpm.llc) hits the app, middleware rewrites
 * to /careers/_custom?domain=jobs.hcpm.llc. This page resolves the domain to
 * a career page slug via the API, then renders that career page inline.
 */
export default function CustomDomainPage() {
  const searchParams = useSearchParams();
  const domain = searchParams.get("domain");
  const [slug, setSlug] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!domain) {
      setError(true);
      return;
    }
    fetch(`${API}/api/public/career-pages/resolve-domain/${domain}`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((data) => setSlug(data.slug))
      .catch(() => setError(true));
  }, [domain]);

  // Once we have the slug, redirect internally to the career page
  useEffect(() => {
    if (slug) {
      // Use window.location.replace to load the career page without adding
      // to browser history. The middleware will allow /careers/* through.
      window.location.replace(`/careers/${slug}`);
    }
  }, [slug]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Page Not Found</h1>
          <p className="text-gray-600">No career page is configured for this domain.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
    </div>
  );
}
