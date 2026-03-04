// Employer pipeline statuses
export const PIPELINE_STATUSES = [
  "silver_medalist",
  "warm_lead",
  "nurturing",
  "contacted",
  "hired",
] as const;

export type PipelineStatus = (typeof PIPELINE_STATUSES)[number];

export const PIPELINE_STATUS_LABELS: Record<PipelineStatus, string> = {
  silver_medalist: "Silver Medalist",
  warm_lead: "Warm Lead",
  nurturing: "Nurturing",
  contacted: "Contacted",
  hired: "Hired",
};

export const PIPELINE_STATUS_COLORS: Record<
  PipelineStatus,
  { bg: string; text: string }
> = {
  silver_medalist: { bg: "#FEF3C7", text: "#92400E" },
  warm_lead: { bg: "#DBEAFE", text: "#1E40AF" },
  nurturing: { bg: "#F3E8FF", text: "#6B21A8" },
  contacted: { bg: "#D1FAE5", text: "#065F46" },
  hired: { bg: "#DCFCE7", text: "#166534" },
};

// Company sizes for employer settings
export const COMPANY_SIZES = [
  "1-10",
  "11-50",
  "51-200",
  "201-500",
  "501-1000",
  "1000+",
];

// Industries for employer settings
export const INDUSTRIES = [
  "Aerospace & Defense",
  "Agriculture",
  "Automotive",
  "Construction",
  "Consulting",
  "Consumer Goods",
  "Education",
  "Energy & Utilities",
  "Entertainment & Media",
  "Financial Services",
  "Food & Beverage",
  "Government",
  "Healthcare",
  "Hospitality & Tourism",
  "Insurance",
  "Legal",
  "Logistics & Transportation",
  "Manufacturing",
  "Mining & Metals",
  "Nonprofit",
  "Pharmaceuticals",
  "Professional Services",
  "Real Estate",
  "Retail & E-Commerce",
  "Technology",
  "Telecommunications",
  "Other",
];

// API response types

export interface PipelineEntry {
  id: number;
  candidate_profile_id: number | null;
  pipeline_status: string;
  match_score: number | null;
  tags: string[] | null;
  notes: string | null;
  source_job_id: number | null;
  last_contacted_at: string | null;
  next_followup_at: string | null;
  consent_given: boolean;
  created_at: string;
}

export interface AnalyticsOverview {
  active_jobs: number;
  total_impressions: number;
  total_clicks: number;
  total_applications: number;
  total_cost: number;
}

export interface CostMetrics {
  total_cost: number;
  total_clicks: number;
  total_applications: number;
  cost_per_click: number;
  cost_per_application: number;
}

export interface BoardRecommendation {
  board_connection_id: number;
  total_applications: number;
  total_clicks: number;
  cost_per_application: number;
  recommendation: string;
}

export interface SavedCandidate {
  id: number;
  candidate_id: number;
  notes: string | null;
  saved_at: string;
  candidate: {
    name: string;
    headline: string | null;
    location: string | null;
    years_experience: number | null;
    top_skills: string[];
    profile_visibility: string;
  } | null;
}

export interface EmployerSubscription {
  tier: string;
  status: string;
  has_subscription: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface EmployerProfile {
  id: number;
  company_name: string;
  company_size: string | null;
  industry: string | null;
  company_website: string | null;
  billing_email: string | null;
  company_description: string | null;
  subscription_tier: string;
  subscription_status: string;
}

export interface FunnelStage {
  stage: string;
  count: number;
}

export interface FunnelData {
  stages: FunnelStage[];
  total: number;
}

export interface AnalyticsRecommendation {
  title: string;
  description: string;
  priority: string;
}
