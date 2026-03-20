import { request } from "./client";
import type {
  CandidateSearchResponse,
  MatchCardSummary,
  RecommendationBatchCreateResponse,
  RecommendationCandidateItem,
  RecommendationHistoryItem
} from "../types/recommendation";

export interface CandidateSearchQuery {
  user_id: number;
  search?: string;
  city?: string;
  age_min?: number;
  age_max?: number;
  page?: number;
  page_size?: number;
}

export function getCandidateSearch(query: CandidateSearchQuery) {
  return request<CandidateSearchResponse>("/api/v1/recommendations/candidate-search/", {
    query: query as Record<string, string | number | undefined>
  });
}

export function getRecommendationHistory(userId: number) {
  return request<RecommendationHistoryItem[]>("/api/v1/recommendations/", {
    query: { user_id: userId }
  });
}

export function createRecommendationBatch(payload: {
  user_id: number;
  candidate_user_ids: number[];
}) {
  return request<RecommendationBatchCreateResponse>("/api/v1/recommendations/", {
    method: "POST",
    body: payload
  });
}

export function selectRecommendationCandidate(candidateId: number) {
  return request<RecommendationCandidateItem>(`/api/v1/recommendations/candidates/${candidateId}/select/`, {
    method: "POST"
  });
}

export function createMatchCard(payload: {
  male_user_id: number;
  female_user_id: number;
  candidate_id: number;
}) {
  return request<MatchCardSummary>("/api/v1/match-cards/", {
    method: "POST",
    body: payload
  });
}
