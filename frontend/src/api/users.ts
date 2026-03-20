import { request } from "./client";
import type { PaginatedResponse, UserDetail, UserListItem } from "../types/user";

export type UserOrdering = "priority_score" | "-priority_score";

export interface UserListQuery {
  page?: number;
  page_size?: number;
  ordering?: UserOrdering;
}

export function getUsers(query: UserListQuery) {
  return request<PaginatedResponse<UserListItem>>("/api/v1/users/", {
    query: query as Record<string, string | number | undefined>
  });
}

export function getUserDetail(id: string) {
  return request<UserDetail>(`/api/v1/users/${id}/`);
}
