export interface TransferRequestItem {
  id: number;
  user_id: number;
  user_name?: string | null;
  from_staff_id: number;
  from_staff_name?: string | null;
  to_staff_id: number;
  to_staff_name?: string | null;
  reason: string;
  status: "pending" | "approved" | "rejected";
  reviewer_id?: number | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
}

export type TransferRequestListResponse = TransferRequestItem[];

export interface TransferApproveAffectedMatchCard {
  id: number;
  updated_field: string;
  new_staff_name?: string | null;
}

export interface TransferApproveResponse {
  id: number;
  status: "approved";
  reviewed_at?: string | null;
  message?: string | null;
  affected_match_cards?: TransferApproveAffectedMatchCard[];
}

export interface TransferRejectResponse {
  id: number;
  status: "rejected";
  review_note?: string | null;
  reviewed_at?: string | null;
}
