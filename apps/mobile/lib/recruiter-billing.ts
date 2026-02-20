import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import type { RecruiterPlan } from "./recruiter-types";

export function useRecruiterBilling() {
  const [plan, setPlan] = useState<RecruiterPlan | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get("/api/recruiter/plan");
      if (res.ok) {
        setPlan(await res.json());
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    tier: plan?.tier ?? "free",
    status: plan?.status ?? "inactive",
    trialActive: plan?.trial_active ?? false,
    trialDaysRemaining: plan?.trial_days_remaining ?? 0,
    usage: plan?.usage ?? {},
    limits: plan?.limits ?? {},
    loading,
    refresh,
  };
}
