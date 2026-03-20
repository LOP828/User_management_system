export interface MatchCardFollowUpItem {
  id: number;
  staff_name?: string | null;
  content?: string | null;
  is_still_contact?: string | null;
  risk_status?: string | null;
  next_remind_mode?: string | null;
  created_at?: string | null;
}

export interface MatchCardDetail {
  id: number;
  male_user_id: number;
  male_user_name?: string | null;
  female_user_id: number;
  female_user_name?: string | null;
  primary_staff_id?: number | null;
  primary_staff_name?: string | null;
  stage: string;
  stage_display?: string | null;
  risk_level: string;
  risk_level_display?: string | null;
  next_remind_at?: string | null;
  created_at: string;
  follow_ups?: MatchCardFollowUpItem[];
  valid_visit_count?: number;
}

export interface FollowUpRecord {
  id: number;
  scene: string;
  match_card_id?: number | null;
  user_id?: number | null;
  staff_id?: number | null;
  staff_name?: string | null;
  content?: string | null;
  is_still_contact?: string | null;
  risk_status?: string | null;
  next_remind_mode?: string | null;
  next_remind_at?: string | null;
  is_valid_visit?: boolean;
  failure_reason_id?: number | null;
  overdue_reason_id?: number | null;
  overdue_reason_note?: string | null;
  created_at?: string | null;
}

export interface MatchedFollowUpCreatePayload {
  scene: "matched";
  match_card_id: number;
  user_id: number;
  content: string;
  is_still_contact: "yes" | "no" | "unknown";
  risk_status: "none" | "watching" | "high_risk";
  next_remind_mode: "manual" | "default";
  next_remind_at?: string;
}

export interface FollowUpUpdatePayload {
  content?: string;
  next_remind_mode?: "manual" | "default";
  next_remind_at?: string | null;
}
