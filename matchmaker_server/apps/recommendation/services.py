from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import BusinessRuleError
from apps.oplog.services import (
    ACTION_CANDIDATE_SELECTED,
    ACTION_RECOMMENDATION_BATCH_CLOSED,
    ACTION_RECOMMENDATION_CREATED,
    create_operation_log,
)
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.staff.models import Staff
from apps.user.models import CustomerProfile
from apps.user.services import append_recommendation_tag, assert_user_owner_or_admin, persist_user_status_change


def _require_batch_access(actor, batch):
    """Matchmaker can only access batches they created; admin has global access."""
    if actor.role == Staff.ROLE_ADMIN:
        return
    if batch.staff_id != actor.id:
        raise PermissionDenied("无权限")


def build_recommendation_batch_queryset(actor, queryset):
    if actor.role == Staff.ROLE_ADMIN:
        return queryset
    return queryset.filter(Q(staff_id=actor.id) | Q(user__owner_id=actor.id)).distinct()


def _raise_batch_already_has_selected_candidate():
    raise BusinessRuleError(
        "BATCH_ALREADY_HAS_SELECTED_CANDIDATE",
        "当前推荐批次已选中过候选人，不能重复选中",
        status.HTTP_400_BAD_REQUEST,
    )


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


def _validate_candidate_user_ids(user, candidate_user_ids):
    unique_ids = list(dict.fromkeys(candidate_user_ids))
    if not unique_ids:
        raise BusinessRuleError(
            "CANDIDATE_LIST_REQUIRED",
            "至少需要一个候选人",
            status.HTTP_400_BAD_REQUEST,
        )

    candidates = list(CustomerProfile.objects.filter(id__in=unique_ids))
    candidate_map = {candidate.id: candidate for candidate in candidates}
    missing = [str(cid) for cid in unique_ids if cid not in candidate_map]
    if missing:
        raise BusinessRuleError(
            "CANDIDATE_NOT_FOUND",
            f"候选人不存在：{', '.join(missing)}",
            status.HTTP_400_BAD_REQUEST,
        )
    deleted = [
        str(cid)
        for cid in unique_ids
        if candidate_map[cid].deleted_at is not None
    ]
    if deleted:
        raise BusinessRuleError(
            "CANDIDATE_DELETED",
            f"候选人已被软删除：{', '.join(deleted)}",
            status.HTTP_400_BAD_REQUEST,
        )

    ordered_candidates = [candidate_map[cid] for cid in unique_ids]
    for candidate in ordered_candidates:
        if candidate.id == user.id:
            raise BusinessRuleError(
                "CANDIDATE_INVALID",
                "候选人不得是当前用户",
                status.HTTP_400_BAD_REQUEST,
            )
        if candidate.pool_status == CustomerProfile.STATUS_PAUSED:
            raise BusinessRuleError(
                "CANDIDATE_PAUSED",
                "候选人处于暂停状态，不能推荐",
                status.HTTP_400_BAD_REQUEST,
            )
        if candidate.is_in_match:
            raise BusinessRuleError(
                "CANDIDATE_IN_MATCH",
                "候选人已在配对中，不能再次推荐",
                status.HTTP_400_BAD_REQUEST,
            )
        if candidate.gender == user.gender:
            raise BusinessRuleError(
                "CANDIDATE_GENDER_MISMATCH",
                "候选人性别必须与当前用户不同",
                status.HTTP_400_BAD_REQUEST,
            )
        if candidate.deleted_at:
            raise BusinessRuleError(
                "CANDIDATE_DELETED",
                "候选人已被软删除",
                status.HTTP_400_BAD_REQUEST,
            )
    return ordered_candidates


def get_candidate_search_target_user(*, actor, user_id):
    try:
        user = CustomerProfile.objects.select_related("payment_level", "owner").get(
            id=user_id,
            deleted_at__isnull=True,
        )
    except CustomerProfile.DoesNotExist as exc:
        raise BusinessRuleError("USER_NOT_FOUND", "用户不存在", status.HTTP_404_NOT_FOUND) from exc
    assert_user_owner_or_admin(actor, user)
    return user


def build_candidate_search_queryset(*, target_user, search=None, city=None, age_min=None, age_max=None):
    queryset = (
        CustomerProfile.objects.filter(deleted_at__isnull=True, is_in_match=False)
        .exclude(pool_status=CustomerProfile.STATUS_PAUSED)
        .exclude(gender=target_user.gender)
        .exclude(id=target_user.id)
        .select_related("payment_level", "owner")
        .order_by("-last_action_at", "-id")
    )

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(phone__icontains=search) | Q(wechat__icontains=search)
        )
    if city:
        queryset = queryset.filter(city=city)
    if age_min is not None:
        queryset = queryset.filter(age__gte=age_min)
    if age_max is not None:
        queryset = queryset.filter(age__lte=age_max)

    return queryset


def build_candidate_duplicate_warning_map(*, target_user, candidates):
    candidate_ids = [candidate.id for candidate in candidates]
    if not candidate_ids:
        return {}

    history = (
        RecommendationCandidate.objects.filter(
            batch__user_id=target_user.id,
            candidate_user_id__in=candidate_ids,
        )
        .select_related("batch")
        .order_by("candidate_user_id", "-batch__created_at", "-id")
    )

    warning_map = {}
    for record in history:
        if record.candidate_user_id in warning_map:
            continue
        if record.is_met:
            if record.result != RecommendationCandidate.RESULT_NOT_CONTINUE:
                continue
            warning_map[record.candidate_user_id] = {
                "level": "danger",
                "message": "该候选人曾见面但未继续",
                "last_batch_date": timezone.localdate(record.batch.created_at).isoformat(),
            }
            continue
        warning_map[record.candidate_user_id] = {
            "level": "warning",
            "message": "该候选人曾被推荐但未见面",
            "last_batch_date": timezone.localdate(record.batch.created_at).isoformat(),
        }

    return warning_map


_MAX_BATCH_NO_RETRIES = 5


def create_recommendation_batch(*, actor, user_id, candidate_user_ids):
    """
    Create a recommendation batch with candidates, retrying on batch_no uniqueness collision.

    BR-REC-001: user pool_status == communicated_pending_recommend AND is_profile_complete
    BR-REC-002: len(candidates) <= payment_level.recommend_limit
    BR-REC-003: duplicate detection — warning only, not blocking
    BR-REC-006: update last_action_at
    Addendum §3: update last_unmatched_active_at on batch creation
    """
    last_exc = None
    for _ in range(_MAX_BATCH_NO_RETRIES):
        try:
            return _create_recommendation_batch_inner(
                actor=actor, user_id=user_id, candidate_user_ids=candidate_user_ids
            )
        except IntegrityError as exc:
            if "batch_no" not in str(exc).lower():
                raise
            last_exc = exc
    raise last_exc  # type: ignore[misc]


@transaction.atomic
def _create_recommendation_batch_inner(*, actor, user_id, candidate_user_ids):
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

    if len(candidate_user_ids) != len(set(candidate_user_ids)):
        raise BusinessRuleError(
            "CANDIDATE_DUPLICATE_INPUT",
            "候选人列表中包含重复 ID",
            status.HTTP_400_BAD_REQUEST,
        )
    unique_candidate_ids = list(dict.fromkeys(candidate_user_ids))
    # BR-REC-002
    recommend_limit = user.payment_level.recommend_limit
    if len(unique_candidate_ids) > recommend_limit:
        raise BusinessRuleError(
            "BR_REC_002",
            f"候选人数量超过套餐限制（最多 {recommend_limit} 人）",
        )

    # BR-REC-003: duplicate detection (warning only, not blocking)
    previous_candidate_ids = set(
        RecommendationCandidate.objects.filter(batch__user_id=user_id).values_list("candidate_user_id", flat=True)
    )
    duplicate_ids = [cid for cid in unique_candidate_ids if cid in previous_candidate_ids]

    now = timezone.now()
    batch_no = _generate_batch_no(now.strftime("%Y%m%d"))

    batch = RecommendationBatch.objects.create(
        user=user,
        staff=actor,
        batch_no=batch_no,
        candidate_count=len(unique_candidate_ids),
        status=RecommendationBatch.STATUS_OPEN,
    )

    candidate_users = _validate_candidate_user_ids(user, unique_candidate_ids)
    RecommendationCandidate.objects.bulk_create(
        [RecommendationCandidate(batch=batch, candidate_user=cand) for cand in candidate_users]
    )

    # Advance user status and update timestamps
    persist_user_status_change(
        user,
        actor,
        to_status=CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT,
    )

    create_operation_log(
        operator=actor,
        action=ACTION_RECOMMENDATION_CREATED,
        target_type="recommendation_batch",
        target_id=batch.id,
        after_json={"batch_no": batch_no, "candidate_count": len(unique_candidate_ids)},
    )

    return batch, duplicate_ids


@transaction.atomic
def select_candidate(*, actor, candidate_id):
    """
    Mark a recommendation candidate as selected.

    Business flow S3→S4: advances user pool_status to selected_pending_meet.
    """
    try:
        candidate = RecommendationCandidate.objects.select_related("batch__user").select_for_update().get(id=candidate_id)
    except RecommendationCandidate.DoesNotExist:
        raise BusinessRuleError("CANDIDATE_NOT_FOUND", "候选人不存在", 404)

    _require_batch_access(actor, candidate.batch)

    if candidate.batch.status != RecommendationBatch.STATUS_OPEN:
        raise BusinessRuleError("BATCH_CLOSED", "批次已关闭，无法操作")

    batch_candidates = RecommendationCandidate.objects.select_for_update().filter(batch_id=candidate.batch_id)
    if candidate.is_selected or batch_candidates.exclude(id=candidate.id).filter(is_selected=True).exists():
        _raise_batch_already_has_selected_candidate()

    candidate.is_selected = True
    try:
        candidate.save(update_fields=["is_selected", "updated_at"])
    except IntegrityError as exc:
        if "rec_batch_single_selected_candidate" not in str(exc) and "recommendation_candidate.batch_id" not in str(exc):
            raise
        _raise_batch_already_has_selected_candidate()

    # S3 → S4: advance user pool_status to selected_pending_meet
    persist_user_status_change(
        candidate.batch.user,
        actor,
        to_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )

    create_operation_log(
        operator=actor,
        action=ACTION_CANDIDATE_SELECTED,
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
        persist_user_status_change(
            batch.user,
            actor,
            to_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            reason="推荐批次关闭",
            tag_editor=append_recommendation_tag,
        )

    create_operation_log(
        operator=actor,
        action=ACTION_RECOMMENDATION_BATCH_CLOSED,
        target_type="recommendation_batch",
        target_id=batch.id,
        after_json={"status": "closed", "has_selected": has_selected},
    )

    return batch


def mark_candidate_continue(candidate):
    if not candidate.is_met or candidate.result != RecommendationCandidate.RESULT_CONTINUE:
        candidate.is_met = True
        candidate.result = RecommendationCandidate.RESULT_CONTINUE
        candidate.save(update_fields=["is_met", "result", "updated_at"])


def mark_selected_candidate_not_continue(user):
    candidate = (
        RecommendationCandidate.objects.filter(
            batch__user_id=user.id,
            is_selected=True,
            result__isnull=True,
        )
        .order_by("-updated_at")
        .first()
    )
    if candidate:
        candidate.is_met = True
        candidate.result = RecommendationCandidate.RESULT_NOT_CONTINUE
        candidate.save(update_fields=["is_met", "result", "updated_at"])
    return candidate
