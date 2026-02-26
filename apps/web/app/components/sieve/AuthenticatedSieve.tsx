"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import SieveWidget from "./SieveWidget";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface SieveTrigger {
  id: string;
  message: string;
  priority: number;
  action_label: string;
  action_type: string;
  action_target: string;
}

export default function AuthenticatedSieve() {
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [triggers, setTriggers] = useState<SieveTrigger[]>([]);

  const fetchTriggers = useCallback((dismissedIds: string[] = []) => {
    fetch(`${API_BASE}/api/sieve/triggers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ dismissed_ids: dismissedIds }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.triggers) setTriggers(data.triggers);
      })
      .catch(() => {});
  }, []);

  // Hide Sieve on public pages
  const PUBLIC_PATHS = ["/", "/login", "/signup", "/terms", "/privacy"];
  const isPublicPage =
    PUBLIC_PATHS.includes(pathname) || pathname.startsWith("/privacy/");

  useEffect(() => {
    if (isPublicPage) return;
    fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })
      .then((res) => {
        if (res.ok) {
          setIsAuthenticated(true);
          fetchTriggers();
        }
      })
      .catch(() => {});
  }, [fetchTriggers, isPublicPage]);

  if (!isAuthenticated || isPublicPage) return null;

  return (
    <SieveWidget
      apiBase={API_BASE}
      triggers={triggers}
      onRefreshTriggers={fetchTriggers}
    />
  );
}
