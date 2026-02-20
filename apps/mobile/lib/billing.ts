import { useState, useEffect, useCallback } from "react";
import { api } from "./api";

interface BillingFeatures {
  data_export: boolean;
  career_intelligence: boolean;
  ips_detail: string;
}

interface BillingUsage {
  match_refreshes: number;
  tailor_requests: number;
  sieve_messages_today: number;
  semantic_searches_today: number;
}

interface BillingState {
  planTier: string;
  billingCycle: string | null;
  subscriptionStatus: string | null;
  features: BillingFeatures;
  usage: BillingUsage;
  limits: Record<string, number>;
  loading: boolean;
}

const DEFAULT_FEATURES: BillingFeatures = {
  data_export: false,
  career_intelligence: false,
  ips_detail: "score_only",
};

const DEFAULT_USAGE: BillingUsage = {
  match_refreshes: 0,
  tailor_requests: 0,
  sieve_messages_today: 0,
  semantic_searches_today: 0,
};

export function useBilling() {
  const [state, setState] = useState<BillingState>({
    planTier: "free",
    billingCycle: null,
    subscriptionStatus: null,
    features: DEFAULT_FEATURES,
    usage: DEFAULT_USAGE,
    limits: {},
    loading: true,
  });

  const refresh = useCallback(async () => {
    try {
      const res = await api.get("/api/billing/status");
      if (res.ok) {
        const data = await res.json();
        setState({
          planTier: data.plan_tier || "free",
          billingCycle: data.billing_cycle || null,
          subscriptionStatus: data.subscription_status || null,
          features: data.features || DEFAULT_FEATURES,
          usage: data.usage || DEFAULT_USAGE,
          limits: data.limits || {},
          loading: false,
        });
      } else {
        setState((prev) => ({ ...prev, loading: false }));
      }
    } catch {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { ...state, refresh };
}
