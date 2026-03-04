// Pipeline stages
export const PIPELINE_STAGES = [
  "sourced",
  "contacted",
  "screening",
  "interviewing",
  "offered",
  "placed",
  "rejected",
] as const;

export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export const STAGE_COLORS: Record<PipelineStage, string> = {
  sourced: "#6B7280",
  contacted: "#3B82F6",
  screening: "#F59E0B",
  interviewing: "#8B5CF6",
  offered: "#22C55E",
  placed: "#16A34A",
  rejected: "#EF4444",
};

export const STAGE_LABELS: Record<PipelineStage, string> = {
  sourced: "Sourced",
  contacted: "Contacted",
  screening: "Screening",
  interviewing: "Interviewing",
  offered: "Offered",
  placed: "Placed",
  rejected: "Rejected",
};

// Job statuses
export const JOB_STATUSES = [
  "draft",
  "active",
  "paused",
  "closed",
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];

export const JOB_STATUS_COLORS: Record<JobStatus, string> = {
  draft: "#6B7280",
  active: "#22C55E",
  paused: "#F59E0B",
  closed: "#EF4444",
};

// Client statuses
export const CLIENT_STATUSES = [
  "active",
  "inactive",
  "prospect",
] as const;

export type ClientStatus = (typeof CLIENT_STATUSES)[number];

export const CLIENT_STATUS_COLORS: Record<ClientStatus, string> = {
  active: "#22C55E",
  inactive: "#6B7280",
  prospect: "#3B82F6",
};

// API response types

export interface DashboardStats {
  total_active_jobs: number;
  total_pipeline_candidates: number;
  total_clients: number;
  total_placements: number;
  pipeline_by_stage: Record<string, number>;
  recent_activities: Activity[];
  subscription_tier: string;
}

export interface RecruiterProfile {
  id: number;
  company_name: string;
  company_type: string | null;
  company_website: string | null;
  specializations: string[] | null;
  subscription_tier: string;
  subscription_status: string;
  is_trial_active: boolean;
  trial_days_remaining: number;
  seats_purchased: number;
  seats_used: number;
  auto_populate_pipeline: boolean;
}

export interface PipelineCandidate {
  id: number;
  recruiter_job_id: number | null;
  candidate_profile_id: number | null;
  external_name: string | null;
  external_email: string | null;
  external_phone: string | null;
  external_linkedin: string | null;
  source: string;
  stage: PipelineStage;
  rating: number | null;
  tags: string[] | null;
  notes: string | null;
  match_score: number | null;
  outreach_count: number;
  candidate_name: string | null;
  headline: string | null;
  location: string | null;
  current_company: string | null;
  skills: string[] | null;
  linkedin_url: string | null;
  is_platform_candidate: boolean;
  created_at: string;
}

export interface RecruiterJob {
  id: number;
  title: string;
  status: JobStatus;
  client_company_name: string | null;
  client_id: number | null;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  priority: string | null;
  positions_to_fill: number;
  positions_filled: number;
  matched_candidates_count: number;
  created_at: string;
  closes_at: string | null;
  description: string | null;
  requirements: string | null;
}

export interface ClientContact {
  name: string;
  email: string | null;
  phone: string | null;
  role: string | null;
}

export interface Client {
  id: number;
  company_name: string;
  industry: string | null;
  contacts: ClientContact[] | null;
  contact_name: string | null;
  contact_email: string | null;
  contract_type: string | null;
  fee_percentage: number | null;
  notes: string | null;
  status: ClientStatus;
  website: string | null;
  job_count: number;
  created_at: string;
}

export interface TeamMember {
  id: number;
  user_id: number | null;
  role: string;
  email: string;
  invited_at: string;
  accepted_at: string | null;
}

export interface Activity {
  id: number;
  activity_type: string;
  subject: string;
  body: string | null;
  created_at: string;
}

export interface RecruiterPlan {
  tier: string;
  status: string;
  trial_active: boolean;
  trial_days_remaining: number;
  usage: Record<string, number>;
  limits: Record<string, number | null>;
}

export interface OutreachStep {
  id: number;
  step_number: number;
  delay_days: number;
  subject: string;
  body: string;
  channel: string;
}

export interface OutreachSequence {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  steps: OutreachStep[];
  total_enrolled: number;
  total_sent: number;
  created_at: string;
}

export interface OutreachEnrollment {
  id: number;
  sequence_id: number;
  candidate_name: string | null;
  candidate_email: string | null;
  current_step: number;
  status: string;
  enrolled_at: string;
}
