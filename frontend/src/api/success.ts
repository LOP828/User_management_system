import { request } from "./client";
import type {
  ReasonEnumListResponse,
  SuccessApplicationListResponse,
  SuccessApproveResponse,
  SuccessCaseDetail,
  SuccessCaseListResponse,
  SuccessInvalidateResponse,
  SuccessRejectResponse
} from "../types/success";

export function getSuccessApplications(status?: string) {
  return request<SuccessApplicationListResponse>("/api/v1/success-applications/", {
    query: {
      status
    }
  });
}

export function approveSuccessApplication(id: number) {
  return request<SuccessApproveResponse>(`/api/v1/success-applications/${id}/approve/`, {
    method: "POST",
    body: {}
  });
}

export function rejectSuccessApplication(id: number, review_note: string) {
  return request<SuccessRejectResponse>(`/api/v1/success-applications/${id}/reject/`, {
    method: "POST",
    body: { review_note }
  });
}

export function getSuccessCases() {
  return request<SuccessCaseListResponse>("/api/v1/success-cases/");
}

export function getSuccessCaseDetail(id: number) {
  return request<SuccessCaseDetail>(`/api/v1/success-cases/${id}/`);
}

export function invalidateSuccessCase(id: number, reason_id: number, reason_note?: string) {
  return request<SuccessInvalidateResponse>(`/api/v1/success-cases/${id}/invalidate/`, {
    method: "POST",
    body: {
      reason_id,
      ...(reason_note?.trim() ? { reason_note: reason_note.trim() } : {})
    }
  });
}

export function getSuccessInvalidateReasons() {
  return request<ReasonEnumListResponse>("/api/v1/reason-enums/", {
    query: {
      category: "success_invalidate",
      is_active: "true"
    }
  });
}
