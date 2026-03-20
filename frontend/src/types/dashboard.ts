export interface DashboardUserPoolStats {
  new_pending: number;
  communicated_pending_recommend: number;
  recommended_pending_select: number;
  selected_pending_meet: number;
  met_not_continue: number;
  paused: number;
}

export interface DashboardMatchCardsAdminStats {
  active: number;
  success_pending_review: number;
  success: number;
  high_risk: number;
}

export interface DashboardMatchCardsMatchmakerStats {
  active: number;
  success_pending_review: number;
}

export interface DashboardRemindersStats {
  pending: number;
}

export interface DashboardPendingApprovals {
  transfer_count: number;
  success_count: number;
}

export interface DashboardOverdueStaffItem {
  staff_id: number;
  staff_name: string;
  overdue_count: number;
}

export interface DashboardOverdueSummary {
  total_overdue_users: number;
  by_staff: DashboardOverdueStaffItem[];
}

export interface DashboardUnmatchedOverdueItem {
  user_id: number;
  user_name: string;
  pool_status_display?: string | null;
  payment_level_name?: string | null;
  overdue_days: number;
  overdue_type?: string | null;
  priority_score?: number | null;
}

export interface DashboardMatchedPendingVisitItem {
  match_card_id: number;
  male_name?: string | null;
  female_name?: string | null;
  stage_display?: string | null;
  risk_level_display?: string | null;
  last_visit_at?: string | null;
  next_remind_at?: string | null;
  overdue_days?: number | null;
  priority_score?: number | null;
}

export interface DashboardRecentNewItem {
  user_id: number;
  user_name: string;
  created_at?: string | null;
}

export interface AdminDashboardResponse {
  user_pool: DashboardUserPoolStats;
  match_cards: DashboardMatchCardsAdminStats;
  reminders: DashboardRemindersStats;
  pending_approvals: DashboardPendingApprovals;
  overdue_summary: DashboardOverdueSummary;
}

export interface MatchmakerDashboardResponse {
  user_pool: DashboardUserPoolStats;
  match_cards: DashboardMatchCardsMatchmakerStats;
  reminders: DashboardRemindersStats;
  unmatched_overdue: {
    count: number;
    items: DashboardUnmatchedOverdueItem[];
  };
  matched_pending_visit: {
    count: number;
    items: DashboardMatchedPendingVisitItem[];
  };
  today_processed: {
    count: number;
  };
  recent_new: {
    count: number;
    items: DashboardRecentNewItem[];
  };
}
