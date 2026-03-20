import { request } from "./client";
import type { MatchCardDetail } from "../types/matchCard";

export function getMatchCardDetail(id: string) {
  return request<MatchCardDetail>(`/api/v1/match-cards/${id}/`);
}
