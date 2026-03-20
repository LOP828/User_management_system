export interface SuccessApplicationItem {
  id: number;
  match_card_id: number;
  applicant_id?: number | null;
  applicant_name?: string | null;
  apply_note?: string | null;
  status: "pending" | "approved" | "rejected";
  review_note?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
}

export interface SuccessApplicationListResponse {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: SuccessApplicationItem[];
}

export interface SuccessApproveResponse {
  id: number;
  status: "approved";
  reviewed_at?: string | null;
  success_case_id?: number | null;
  message?: string | null;
}

export interface SuccessRejectResponse {
  id: number;
  status: "rejected";
  review_note?: string | null;
  reviewed_at?: string | null;
  message?: string | null;
}

export interface SuccessCaseListItem {
  id: number;
  application_id?: number | null;
  match_card_id: number;
  status: "active" | "invalidated";
  approved_at?: string | null;
  invalidated_reason_id?: number | null;
  invalidated_reason_label?: string | null;
  invalidated_reason_note?: string | null;
  invalidated_at?: string | null;
  updated_at?: string | null;
}

export interface SuccessCaseListResponse {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: SuccessCaseListItem[];
}

export interface SuccessCaseFollowUpItem {
  id: number;
  staff_name?: string | null;
  content?: string | null;
  is_still_contact?: string | null;
  next_remind_mode?: string | null;
  next_remind_at?: string | null;
  is_valid_visit?: boolean;
  created_at?: string | null;
}

export interface SuccessCaseDetail {
  id: number;
  application_id?: number | null;
  match_card_id: number;
  match_card_stage?: string | null;
  male_user_id?: number | null;
  female_user_id?: number | null;
  status: "active" | "invalidated";
  approved_at?: string | null;
  invalidated_reason_label?: string | null;
  invalidated_at?: string | null;
  invalidated_reason_id?: number | null;
  invalidated_reason_note?: string | null;
  updated_at?: string | null;
  follow_ups?: SuccessCaseFollowUpItem[];
}

export interface SuccessInvalidateResponse {
  id: number;
  status: "invalidated";
  invalidated_at?: string | null;
  message?: string | null;
}

export interface ReasonEnumItem {
  id: number;
  category: string;
  label: string;
  is_active: boolean;
}

export interface ReasonEnumListResponse {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: ReasonEnumItem[];
}
