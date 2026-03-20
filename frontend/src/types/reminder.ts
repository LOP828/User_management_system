export interface ReminderItem {
  id: number;
  target_type: "user" | "match_card";
  target_id: number;
  target_name?: string | null;
  target_summary?: string | null;
  staff_id?: number | null;
  remind_type: string;
  remind_type_display?: string | null;
  remind_at?: string | null;
  status: "pending" | "sent" | "processed" | "expired";
  is_manual?: boolean;
  created_at?: string | null;
  processed_at?: string | null;
}

export interface ReminderListResponse {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: ReminderItem[];
}

export interface ReminderProcessResponse {
  id: number;
  status: "processed";
  processed_at?: string | null;
  created_follow_up_id?: number | null;
}
