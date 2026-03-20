import { request } from "./client";
import type {
  FollowUpRecord,
  FollowUpUpdatePayload,
  MatchedFollowUpCreatePayload
} from "../types/matchCard";

interface FollowUpListResponse {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: FollowUpRecord[];
}

export function createMatchedFollowUp(payload: MatchedFollowUpCreatePayload) {
  return request<FollowUpRecord>("/api/v1/follow-ups/", {
    method: "POST",
    body: payload
  });
}

export function getMatchCardMatchedFollowUps(matchCardId: string | number) {
  return request<FollowUpListResponse | FollowUpRecord[]>("/api/v1/follow-ups/", {
    query: {
      match_card_id: matchCardId
    }
  }).then((payload) => Array.isArray(payload)
    ? {
        count: payload.length,
        next: null,
        previous: null,
        results: payload
      }
    : payload);
}

export function getFollowUpDetail(id: string | number) {
  return request<FollowUpRecord>(`/api/v1/follow-ups/${id}/`);
}

export function updateFollowUp(id: string | number, payload: FollowUpUpdatePayload) {
  return request<FollowUpRecord>(`/api/v1/follow-ups/${id}/`, {
    method: "PATCH",
    body: payload
  });
}
