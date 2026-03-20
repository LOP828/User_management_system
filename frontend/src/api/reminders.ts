import { request } from "./client";
import type { ReminderListResponse, ReminderProcessResponse } from "../types/reminder";

interface ReminderListQuery {
  status?: string;
}

export function getReminderList(query?: ReminderListQuery) {
  return request<ReminderListResponse>("/api/v1/reminders/", {
    query: query as Record<string, string | number | undefined> | undefined
  });
}

export function processReminder(id: number) {
  return request<ReminderProcessResponse>(`/api/v1/reminders/${id}/process/`, {
    method: "POST",
    body: {}
  });
}
