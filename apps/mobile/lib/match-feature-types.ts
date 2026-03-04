// Shared TypeScript interfaces for match feature API responses

export interface StatusPrediction {
  predicted_stage: string;
  confidence: number;
  days_since_applied: number;
  explanation: string;
  next_milestone: string;
  tips: string[];
}

export interface InterviewQuestion {
  question: string;
  category: string;
  star_answer?: {
    situation: string;
    task: string;
    action: string;
    result: string;
  };
}

export interface InterviewPrepData {
  status: string;
  questions?: InterviewQuestion[];
  company_insights?: string[];
  gap_strategies?: string[];
  closing_questions?: string[];
  error_message?: string;
}

export interface RejectionFeedbackData {
  status: string;
  interpretation?: string;
  strengths?: string[];
  likely_causes?: string[];
  next_steps?: string[];
  encouragement?: string;
  error_message?: string;
}

export interface CultureSummary {
  summary: string;
  work_style?: string;
  pace?: string;
  remote_policy?: string;
  growth?: string;
  values?: string[];
  signals?: string[];
}

export interface GapResource {
  title: string;
  url?: string;
  type: string;
}

export interface GapSkillRec {
  skill: string;
  priority: string;
  time_estimate: string;
  quick_win: string;
  resources: GapResource[];
}

export interface GapRecommendations {
  status: string;
  overall_strategy?: string;
  skill_recs?: GapSkillRec[];
  error_message?: string;
}

export interface EmailDraft {
  subject: string;
  body: string;
}

export interface SalaryCoachingData {
  offer_assessment: {
    rating: string;
    summary: string;
  };
  negotiation_strategy: string;
  counter_script: string;
  justification_points: string[];
  alternative_asks: string[];
  red_flags: string[];
  green_flags: string[];
  timeline: string;
}

export interface EnhancementSuggestion {
  category: string;
  priority: string;
  issue: string;
  suggestion: string;
  example: string;
  impact: string;
}

export interface EnhancementSuggestionsData {
  status: string;
  overall_assessment?: {
    strengths: string[];
    biggest_opportunity: string;
  };
  suggestions?: EnhancementSuggestion[];
  error_message?: string;
}
