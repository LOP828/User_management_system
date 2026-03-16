from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import BusinessRuleError
from apps.oplog.services import create_operation_log
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.staff.models import Staff
from apps.user.models import CustomerProfile
from apps.user.services import create_status_history


def _require_batch_access(actor, batch):
    """Matchmaker can only access batches they created; admin has global access."""
    if actor.role == Staff.ROLE_ADMIN:
        return
    if batch.staff_id != actor.id:
        raise PermissionDenied("无权限")


def _generate_batch_no(date_str: str) -> str:
    """Generate next sequential batch_no for the given date, e.g. REC-20260316-001."""
    prefix = f"REC-{date_str}-"
    existing_nos = list(
        RecommendationBatch.objects.filter(batch_no__startswith=prefix).values_list("batch_no", flat=True)
    )
    used = {no[len(prefix):] for no in existing_nos}
    seq = 1
    while f"{seq:03d}" in used:
        seq += 1
    return f"{prefix}{seq:03d}"


@transaction.atomic
def create_recommendation_batch(*, actor, user_id, candidate_user_ids):
    """
    Create a recommendation batch with candidates.

    BR-REC-001: user pool_status == communicated_pending_recommend AND is_profile_complete
    BR-REC-002: len(candidates) <= payment_level.recommend_limit
    BR-REC-003: duplicate detection — warning only, not blocking
    BR-REC-006: update last_action_at
    Addendum §3: update last_unmatched_active_at on batch creation
    """
    try:
        user = CustomerProfile.objects.select_related("payment_level").get(id=user_id)
    except CustomerProfile.DoesNotExist:
        raise BusinessRuleError("USER_NOT_FOUND", "用户不存在", 404)

    if actor.role == Staff.ROLE_MATCHMAKER and user.owner_id != actor.id:
        raise PermissionDenied("无权限")

    # BR-REC-001
    if user.pool_status != CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND:
        raise BusinessRuleError(
            "BR_REC_001_STATUS",
            "用户状态必须为 communicated_pending_recommend",
        )
    if not user.is_profile_complete:
        raise BusinessRuleError(
            "BR_REC_001_PROFILE",
            "用户资料未完善，无法推荐",
        )

    # BR-REC-002
    recommend_limit = user.payment_level.recommend_limit
    if len(candidate_user_ids) > recommend_limit:
        raise BusinessRuleError(
            "BR_REC_002",
            f"候选人数量超过套餐限制（最多 {recommend_limit} 人）",
        )

    # BR-REC-003: duplicate detection (warning only, not blocking)
    previous_candidate_ids = set(
        RecommendationCandidate.objects.filter(batch__user_id=user_id).values_list("candidate_user_id", flat=True)
    )
    duplicate_ids = [cid for cid in candidate_user_ids if cid in previous_candidate_ids]

    now = timezone.now()
    batch_no = _generate_batch_no(now.strftime("%Y%m%d"))

    batch = RecommendationBatch.objects.create(
        user=user,
        staff=actor,
        batch_no=batch_no,
        candidate_count=len(candidate_user_ids),
        status=RecommendationBatch.STATUS_OPEN,
    )

    RecommendationCandidate.objects.bulk_create(
        [RecommendationCandidate(batch=batch, candidate_user_id=cid) for cid in candidate_user_ids]
    )

    # Advance user status and update timestamps
    from_status = user.pool_status
    user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    user.last_action_at = now
    user.last_unmatched_active_at = now
    user.save(update_fields=["pool_status", "last_action_at", "last_unmatched_active_at", "updated_at"])
    create_status_history(
        user=user,
        changed_by=actor,
        from_status=from_status,
        to_status=CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT,
    )

    create_operation_log(
        operator=actor,
        action="create_recommendation_batch",
        target_type="recommendation_batch",
        target_id=batch.id,
        after_json={"batch_no": batch_no, "candidate_count": len(candidate_user_ids)},
    )

    return batch, duplicate_ids


@transaction.atomic
def select_candidate(*, actor, candidate_id):
    """
    Mark a recommendation candidate as selected.

    Business flow S3→S4: advances user pool_status to selected_pending_meet.
    """
    try:
        candidate = RecommendationCandidate.objects.select_related("batch__user").get(id=candidate_id)
    except RecommendationCandidate.DoesNotExist:
        raise BusinessRuleError("CANDIDATE_NOT_FOUND", "候选人不存在", 404)

    _require_batch_access(actor, candidate.batch)

    if candidate.batch.status != RecommendationBatch.STATUS_OPEN:
        raise BusinessRuleError("BATCH_CLOSED", "批次已关闭，无法操作")

    candidate.is_selected = True
    candidate.save(update_fields=["is_selected", "updated_at"])

    # S3 → S4: advance user pool_status to selected_pending_meet
    user = candidate.batch.user
    from_status = user.pool_status
    user.pool_status = CustomerProfile.STATUS_SELECTED_PENDING_MEET
    user.save(update_fields=["pool_status", "updated_at"])
    create_status_history(
        user=user,
        changed_by=actor,
        from_status=from_status,
        to_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )

    create_operation_log(
        operator=actor,
        action="select_recommendation_candidate",
        target_type="recommendation_candidate",
        target_id=candidate.id,
    )

    return candidate


@transaction.atomic
def close_recommendation_batch(*, actor, batch_id):
    """
    Close a recommendation batch.

    BR-REC-005: if no candidate is selected, revert user pool_status to
    communicated_pending_recommend.
    """
    try:
        batch = RecommendationBatch.objects.select_related("user").get(id=batch_id)
    except RecommendationBatch.DoesNotExist:
        raise BusinessRuleError("BATCH_NOT_FOUND", "批次不存在", 404)

    _require_batch_access(actor, batch)

    if batch.status == RecommendationBatch.STATUS_CLOSED:
        raise BusinessRuleError("BATCH_ALREADY_CLOSED", "批次已经关闭")

    now = timezone.now()
    batch.status = RecommendationBatch.STATUS_CLOSED
    batch.closed_at = now
    batch.save(update_fields=["status", "closed_at"])

    has_selected = batch.candidates.filter(is_selected=True).exists()

    # BR-REC-005: no selected candidate → revert user to communicated_pending_recommend + 待重新推荐 tag
    if not has_selected:
        user = batch.user
        from_status = user.pool_status
        user.pool_status = CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
        tags = list(user.tags or [])
        if "待重新推荐" not in tags:
            tags.append("待重新推荐")
        user.tags = tags
        user.save(update_fields=["pool_status", "tags", "updated_at"])
        create_status_history(
            user=user,
            changed_by=actor,
            from_status=from_status,
            to_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        )

    create_operation_log(
        operator=actor,
        action="close_recommendation_batch",
        target_type="recommendation_batch",
        target_id=batch.id,
        after_json={"status": "closed", "has_selected": has_selected},
    )

    return batch
