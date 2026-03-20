from apps.oplog.models import OperationLog

# ---------------------------------------------------------------------------
# Canonical action constants（与文档 06_api_contract §4.12.1 对齐）
# ---------------------------------------------------------------------------
ACTION_USER_CREATED = "user_created"
ACTION_USER_STATUS_CHANGED = "user_status_changed"
ACTION_USER_PROFILE_UPDATED = "user_profile_updated"
ACTION_USER_PAUSED = "user_paused"
ACTION_USER_RESUMED = "user_resumed"
ACTION_USER_OWNER_CHANGED = "user_owner_changed"
ACTION_RECOMMENDATION_CREATED = "recommendation_created"
ACTION_CANDIDATE_SELECTED = "candidate_selected"
ACTION_RECOMMENDATION_BATCH_CLOSED = "close_recommendation_batch"
ACTION_MATCH_CARD_CREATED = "match_card_created"
ACTION_MATCH_CARD_STAGE_CHANGED = "match_card_stage_changed"
ACTION_MATCH_CARD_RISK_CHANGED = "match_card_risk_changed"
ACTION_MATCH_CARD_UPDATED = "match_card_updated"
ACTION_MATCH_CARD_ENDED = "match_card_ended"
ACTION_FOLLOW_UP_CREATED = "follow_up_created"
ACTION_FOLLOW_UP_UPDATED = "follow_up_updated"
ACTION_SUCCESS_APPLIED = "success_applied"
ACTION_SUCCESS_APPROVED = "success_approved"
ACTION_SUCCESS_REJECTED = "success_rejected"
ACTION_SUCCESS_INVALIDATED = "success_invalidated"
ACTION_TRANSFER_APPLIED = "transfer_applied"
ACTION_TRANSFER_APPROVED = "transfer_approved"
ACTION_TRANSFER_REJECTED = "transfer_rejected"
ACTION_REMINDER_SET = "reminder_set"
ACTION_ADMIN_FORCE_CHANGE = "admin_force_change"


def create_operation_log(
    *,
    operator,
    action,
    target_type,
    target_id,
    before_json=None,
    after_json=None,
    reason=None,
):
    return OperationLog.objects.create(
        operator=operator,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_json=before_json,
        after_json=after_json,
        reason=reason,
    )
