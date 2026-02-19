"use client";

import { useState, useEffect } from "react";

interface AuthUser {
  user_id: number;
  email: string;
  onboarding_complete: boolean;
  is_admin: boolean;
  role: "candidate" | "employer" | "recruiter" | "both";
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api/auth/me`,
          { credentials: "include" },
        );
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, []);

  const isCandidate =
    user?.role === "candidate" || user?.role === "both";
  const isEmployer =
    user?.role === "employer" || user?.role === "both";
  const isRecruiter = user?.role === "recruiter";
  return { user, loading, isAdmin: user?.is_admin ?? false, isCandidate, isEmployer, isRecruiter };
}
