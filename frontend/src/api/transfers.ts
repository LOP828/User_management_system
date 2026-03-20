import { request } from "./client";
import type {
  TransferApproveResponse,
  TransferRejectResponse,
  TransferRequestListResponse
} from "../types/transfer";

export function getTransferRequests(status?: string) {
  return request<TransferRequestListResponse>("/api/v1/transfer-requests/", {
    query: {
      status
    }
  });
}

export function approveTransferRequest(id: number) {
  return request<TransferApproveResponse>(`/api/v1/transfer-requests/${id}/approve/`, {
    method: "POST",
    body: {}
  });
}

export function rejectTransferRequest(id: number, review_note: string) {
  return request<TransferRejectResponse>(`/api/v1/transfer-requests/${id}/reject/`, {
    method: "POST",
    body: { review_note }
  });
}
