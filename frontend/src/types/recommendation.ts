import type { PaginatedResponse } from "./user";

export interface DuplicateWarning {
  level: string;
  message: string;
  last_batch_date?: string;
}

export interface CandidateSearchItem {
  id: number;
  name: string;
  gender: string;
  age: number;
  city: string;
  payment_level_name?: string | null;
  pool_status_display?: string | null;
  is_profile_complete: boolean;
  duplicate_warning?: DuplicateWarning | null;
}

export type CandidateSearchResponse = PaginatedResponse<CandidateSearchItem>;

export interface RecommendationCandidateItem {
  id: number;
  candidate_user_id: number;
  candidate_user_name: string;
  is_selected: boolean;
  is_met: boolean;
  result?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecommendationHistoryItem {
  id: number;
  user_id: number;
  user_name: string;
  staff_id: number;
  staff_name: string;
  batch_no: string;
  candidate_count: number;
  status: string;
  created_at: string;
  closed_at?: string | null;
  candidates: RecommendationCandidateItem[];
}

export interface RecommendationBatchWarning {
  code: string;
  duplicate_candidate_user_ids?: number[];
}

export interface RecommendationBatchCreateResponse extends RecommendationHistoryItem {
  warnings?: RecommendationBatchWarning[];
}

export interface MatchCardSummary {
  id: number;
  male_user_id: number;
  male_user_name?: string | null;
  female_user_id: number;
  female_user_name?: string | null;
  primary_staff_name?: string | null;
  candidate_id?: number | null;
  candidate_user_id?: number | null;
  candidate_user_name?: string | null;
  stage: string;
  stage_display?: string | null;
  next_remind_at?: string | null;
  created_at: string;
}
