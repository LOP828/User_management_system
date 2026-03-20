import { request } from "./client";
import type { AdminDashboardResponse, MatchmakerDashboardResponse } from "../types/dashboard";

export function getAdminDashboard() {
  return request<AdminDashboardResponse>("/api/v1/dashboard/admin/");
}

export function getMatchmakerDashboard() {
  return request<MatchmakerDashboardResponse>("/api/v1/dashboard/matchmaker/");
}
