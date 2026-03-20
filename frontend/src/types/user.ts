export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  results: T[];
}

export interface FollowUpPreview {
  id: number;
  scene?: string | null;
  content?: string | null;
  created_at?: string | null;
  staff_name?: string | null;
}

export interface ActiveMatchCardPreview {
  id: number;
  stage?: string | null;
  stage_display?: string | null;
  male_user_name?: string | null;
  female_user_name?: string | null;
  primary_staff_name?: string | null;
  next_remind_at?: string | null;
}

export interface UserStats {
  total_recommendations?: number;
  total_meetings?: number;
  total_match_cards?: number;
}

export interface UserListItem {
  id: number;
  name: string;
  gender?: string;
  age?: number;
  city?: string;
  pool_status?: string;
  pool_status_display?: string;
  owner_id?: number;
  owner_name?: string;
  priority_score?: number;
  last_action_at?: string | null;
}

export interface UserDetail extends UserListItem {
  phone?: string;
  wechat?: string;
  other_contact?: string;
  payment_level_name?: string;
  recent_follow_ups?: FollowUpPreview[];
  active_match_card?: ActiveMatchCardPreview | null;
  stats?: UserStats;
  last_unmatched_active_at?: string | null;
  profile_detail?: Record<string, unknown>;
}
