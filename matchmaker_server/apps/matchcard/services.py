from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.services import get_match_card_side_valid_visit_counts
from apps.matchcard.models import MatchCard
from apps.matchcard.permissions import MATCHCARD_EDITABLE_FIELDS, can_view_match_card, get_allowed_update_fields
from apps.oplog.services import create_operation_log
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.recommendation.services import mark_candidate_continue
from apps.reminder.models import Reminder
from apps.reminder.services import expire_target_reminders, sync_match_card_revisit_reminders
from apps.staff.models import Staff
from apps.user.models import CustomerProfile
from apps.user.services import append_recommendation_tag, persist_user_status_change


STAGE_DISPLAY_MAP = {
    MatchCard.STAGE_INITIAL_CONTACT: "初期接触",
    MatchCard.STAGE_STABLE_CONTACT: "稳定联系",
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW: "成功待审核",
    MatchCard.STAGE_SUCCESS: "成功",
    MatchCard.STAGE_ENDED: "结束",
}
RISK_DISPLAY_MAP = {
    MatchCard.RISK_NONE: "无风险",
    MatchCard.RISK_WATCHING: "关注中",
    MatchCard.RISK_HIGH_RISK: "高风险",
}
ALLOWED_STAGE_TRANSITIONS = {
    MatchCard.STAGE_INITIAL_CONTACT: {MatchCard.STAGE_STABLE_CONTACT, MatchCard.STAGE_ENDED},
    MatchCard.STAGE_STABLE_CONTACT: {MatchCard.STAGE_ENDED},
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW: set(),
    MatchCard.STAGE_SUCCESS: {MatchCard.STAGE_ENDED},
    MatchCard.STAGE_ENDED: set(),
}


def _require_candidate_batch_access(actor, candidate):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if candidate.batch.staff_id != actor.id:
        raise PermissionDenied("无权限")


def _resolve_match_card_candidate(actor, male_user, female_user, candidate_id):
    try:
        candidate = RecommendationCandidate.objects.select_related("candidate_user", "batch__user").get(id=candidate_id)
    except RecommendationCandidate.DoesNotExist:
        raise BusinessRuleError("CANDIDATE_NOT_FOUND", "候选人不存在", status.HTTP_400_BAD_REQUEST)

    _require_candidate_batch_access(actor, candidate)

    if candidate.batch.status != RecommendationBatch.STATUS_OPEN:
        raise BusinessRuleError("BATCH_CLOSED", "推荐批次已关闭，无法建卡", status.HTTP_400_BAD_REQUEST)

    expected_ids = {male_user.id, female_user.id}
    actual_ids = {candidate.batch.user_id, candidate.candidate_user_id}
    if expected_ids != actual_ids:
        raise BusinessRuleError(
            "CANDIDATE_MISMATCH",
            "候选人与正在建卡的用户不匹配",
            status.HTTP_400_BAD_REQUEST,
        )

    if not candidate.is_selected:
        raise BusinessRuleError(
            "CANDIDATE_NOT_SELECTED",
            "候选人尚未标记选中",
            status.HTTP_400_BAD_REQUEST,
        )
    if candidate.is_met:
        raise BusinessRuleError(
            "CANDIDATE_ALREADY_PROCESSED",
            "候选人已被处理过",
            status.HTTP_400_BAD_REQUEST,
        )

    return candidate


def build_matchcard_queryset(actor, queryset):
    if actor.role == Staff.ROLE_ADMIN:
        return queryset
    return queryset.filter(
        Q(male_staff_id=actor.id) | Q(female_staff_id=actor.id) | Q(primary_staff_id=actor.id)
    )


def require_matchcard_view_permission(actor, match_card):
    if not can_view_match_card(actor, match_card):
        raise PermissionDenied("无权限")


def require_matchcard_primary_permission(actor, match_card):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id != match_card.primary_staff_id:
        raise PermissionDenied("无权限")


@transaction.atomic
def create_match_card(validated_data, actor):
    male_user = validated_data["male_user"]
    female_user = validated_data["female_user"]
    candidate_id = validated_data["candidate_id"]

    if male_user.id == female_user.id:
        raise ValidationError({"female_user_id": ["男方和女方不能是同一用户。"]})

    if male_user.is_in_match or female_user.is_in_match:
        raise BusinessRuleError(
            "USER_ALREADY_IN_MATCH",
            "用户已在配对中",
            status.HTTP_400_BAD_REQUEST,
        )

    if actor.role != Staff.ROLE_ADMIN and actor.id not in {male_user.owner_id, female_user.owner_id}:
        raise PermissionDenied("无权限")

    if (
        male_user.pool_status != CustomerProfile.STATUS_SELECTED_PENDING_MEET
        and female_user.pool_status != CustomerProfile.STATUS_SELECTED_PENDING_MEET
    ):
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "至少一方用户状态需为 selected_pending_meet",
            status.HTTP_400_BAD_REQUEST,
        )

    candidate = _resolve_match_card_candidate(actor, male_user, female_user, candidate_id)
    now = timezone.now()
    match_card = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_user.owner,
        female_staff=female_user.owner,
        primary_staff=actor,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
        risk_level=MatchCard.RISK_NONE,
        next_remind_at=now + timedelta(days=7),
        recommendation_candidate=candidate,
    )

    male_user.is_in_match = True
    male_user.last_action_at = now
    male_user.save(update_fields=["is_in_match", "last_action_at", "updated_at"])

    female_user.is_in_match = True
    female_user.last_action_at = now
    female_user.save(update_fields=["is_in_match", "last_action_at", "updated_at"])

    create_operation_log(
        operator=actor,
        action="match_card_created",
        target_type="match_card",
        target_id=match_card.id,
        before_json=None,
        after_json={
            "stage": match_card.stage,
            "male_user_id": match_card.male_user_id,
            "female_user_id": match_card.female_user_id,
            "primary_staff_id": match_card.primary_staff_id,
        },
        reason=None,
    )
    sync_match_card_revisit_reminders(match_card)
    mark_candidate_continue(candidate)

    return match_card


def update_match_card(instance, validated_data, actor):
    require_matchcard_view_permission(actor, instance)

    attempted_fields = {field for field, value in validated_data.items() if value is not None}
    if not attempted_fields:
        raise ValidationError({"non_field_errors": ["至少传入一个可更新字段。"]})

    editable_fields = attempted_fields & MATCHCARD_EDITABLE_FIELDS
    if editable_fields != attempted_fields:
        raise PermissionDenied("无权限")

    allowed_fields = get_allowed_update_fields(actor, instance)
    if not attempted_fields.issubset(allowed_fields):
        raise PermissionDenied("无权限")

    # 记录变更前后值（仅实际变化的字段）
    before_json = {}
    after_json = {}
    for field in attempted_fields:
        old_value = getattr(instance, field)
        new_value = validated_data[field]
        if old_value != new_value:
            before_json[field] = old_value
            after_json[field] = new_value

    for field, value in validated_data.items():
        if field in attempted_fields:
            setattr(instance, field, value)

    instance.save(update_fields=[*attempted_fields, "updated_at"])

    if before_json:
        create_operation_log(
            operator=actor,
            action="match_card_updated",
            target_type="match_card",
            target_id=instance.id,
            before_json=before_json,
            after_json=after_json,
            reason=None,
        )

    now = timezone.now()
    instance.male_user.last_action_at = now
    instance.male_user.save(update_fields=["last_action_at", "updated_at"])
    instance.female_user.last_action_at = now
    instance.female_user.save(update_fields=["last_action_at", "updated_at"])

    return instance


def build_stage_response(match_card, message):
    return {
        "id": match_card.id,
        "stage": match_card.stage,
        "stage_display": STAGE_DISPLAY_MAP.get(match_card.stage, match_card.stage),
        "message": message,
    }


def build_risk_response(match_card, message):
    return {
        "id": match_card.id,
        "risk_level": match_card.risk_level,
        "risk_level_display": RISK_DISPLAY_MAP.get(match_card.risk_level, match_card.risk_level),
        "message": message,
    }


def _masked_name(name):
    if not name:
        return ""
    return f"{name[0]}**"


def _append_emotional_history(user, partner_name, match_card):
    history = list(user.emotional_history or [])
    history.append(
        {
            "match_card_id": match_card.id,
            "partner_name": _masked_name(partner_name),
            "start_date": match_card.created_at.date().isoformat(),
            "end_date": match_card.ended_at.date().isoformat(),
            "end_reason": match_card.end_reason_staff,
        }
    )
    user.emotional_history = history


def advance_match_card_stage(match_card, actor, to_stage, reason=""):
    require_matchcard_primary_permission(actor, match_card)

    if to_stage not in {choice[0] for choice in MatchCard.STAGE_CHOICES}:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "配对卡阶段流转不合法",
            status.HTTP_400_BAD_REQUEST,
        )

    if to_stage == MatchCard.STAGE_SUCCESS_PENDING_REVIEW:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "成功待审核只能通过发起成功申请进入",
            status.HTTP_400_BAD_REQUEST,
        )

    if match_card.stage == MatchCard.STAGE_SUCCESS_PENDING_REVIEW:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "成功待审核阶段请通过成功申请审批流程处理",
            status.HTTP_400_BAD_REQUEST,
        )

    if to_stage not in ALLOWED_STAGE_TRANSITIONS.get(match_card.stage, set()):
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "配对卡阶段流转不合法",
            status.HTTP_400_BAD_REQUEST,
        )

    if to_stage == MatchCard.STAGE_ENDED:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "结束配对请使用专用接口",
            status.HTTP_400_BAD_REQUEST,
        )

    valid_visit_counts = get_match_card_side_valid_visit_counts(match_card)
    if match_card.stage == MatchCard.STAGE_INITIAL_CONTACT and to_stage == MatchCard.STAGE_STABLE_CONTACT:
        if valid_visit_counts["male"] < 1 or valid_visit_counts["female"] < 1:
            raise BusinessRuleError(
                "MATCH_NOT_ENOUGH_VISITS",
                "有效回访次数不足",
                status.HTTP_400_BAD_REQUEST,
            )

    before_json = {"stage": match_card.stage}
    match_card.stage = to_stage
    match_card.save(update_fields=["stage", "updated_at"])
    create_operation_log(
        operator=actor,
        action="match_card_stage_changed",
        target_type="match_card",
        target_id=match_card.id,
        before_json=before_json,
        after_json={"stage": match_card.stage},
        reason=reason or None,
    )
    return build_stage_response(match_card, "阶段推进成功")


def set_match_card_risk(match_card, actor, risk_level, risk_reason_id=None, risk_reason_note=None):
    require_matchcard_view_permission(actor, match_card)

    if match_card.stage not in {MatchCard.STAGE_INITIAL_CONTACT, MatchCard.STAGE_STABLE_CONTACT}:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "当前阶段不允许设置风险",
            status.HTTP_400_BAD_REQUEST,
        )

    if risk_level not in {choice[0] for choice in MatchCard.RISK_LEVEL_CHOICES}:
        raise BusinessRuleError(
            "VALIDATION_ERROR",
            "参数校验失败",
            status.HTTP_400_BAD_REQUEST,
            {"risk_level": ["风险等级不合法。"]},
        )

    reason_obj = None
    if risk_level in {MatchCard.RISK_WATCHING, MatchCard.RISK_HIGH_RISK}:
        if not risk_reason_id:
            raise BusinessRuleError(
                "RISK_REASON_REQUIRED",
                "风险标记必须填写原因",
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            reason_obj = ReasonEnum.objects.get(
                id=risk_reason_id,
                category=ReasonEnum.CATEGORY_RISK,
                is_active=True,
            )
        except ReasonEnum.DoesNotExist as exc:
            raise BusinessRuleError(
                "RISK_REASON_REQUIRED",
                "风险标记必须填写原因",
                status.HTTP_400_BAD_REQUEST,
            ) from exc

    before_json = {
        "risk_level": match_card.risk_level,
        "risk_reason_id": match_card.risk_reason_id,
        "risk_reason_note": match_card.risk_reason_note,
    }
    match_card.risk_level = risk_level
    if risk_level == MatchCard.RISK_NONE:
        match_card.risk_reason = None
        match_card.risk_reason_note = None
    else:
        match_card.risk_reason = reason_obj
        match_card.risk_reason_note = risk_reason_note or None
    match_card.save(update_fields=["risk_level", "risk_reason", "risk_reason_note", "updated_at"])

    now = timezone.now()
    match_card.male_user.last_action_at = now
    match_card.male_user.save(update_fields=["last_action_at", "updated_at"])
    match_card.female_user.last_action_at = now
    match_card.female_user.save(update_fields=["last_action_at", "updated_at"])

    create_operation_log(
        operator=actor,
        action="match_card_risk_changed",
        target_type="match_card",
        target_id=match_card.id,
        before_json=before_json,
        after_json={
            "risk_level": match_card.risk_level,
            "risk_reason_id": match_card.risk_reason_id,
            "risk_reason_note": match_card.risk_reason_note,
        },
        reason=match_card.risk_reason_note or (match_card.risk_reason.label if match_card.risk_reason else None),
    )
    return build_risk_response(match_card, "风险标记已更新")


def end_match_card(match_card, actor, end_reason_male=None, end_reason_female=None, end_reason_staff=None):
    require_matchcard_primary_permission(actor, match_card)

    if match_card.stage not in {MatchCard.STAGE_INITIAL_CONTACT, MatchCard.STAGE_STABLE_CONTACT}:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "当前阶段不允许结束配对",
            status.HTTP_400_BAD_REQUEST,
        )
    if not end_reason_staff:
        raise BusinessRuleError(
            "END_REASON_REQUIRED",
            "必须填写结束原因",
            status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    before_json = {
        "stage": match_card.stage,
        "end_reason_male": match_card.end_reason_male,
        "end_reason_female": match_card.end_reason_female,
        "end_reason_staff": match_card.end_reason_staff,
    }
    match_card.stage = MatchCard.STAGE_ENDED
    match_card.ended_at = now
    match_card.end_reason_male = end_reason_male or None
    match_card.end_reason_female = end_reason_female or None
    match_card.end_reason_staff = end_reason_staff
    match_card.next_remind_at = None
    match_card.save(
        update_fields=[
            "stage",
            "ended_at",
            "end_reason_male",
            "end_reason_female",
            "end_reason_staff",
            "next_remind_at",
            "updated_at",
        ]
    )
    expire_target_reminders(Reminder.TARGET_MATCH_CARD, match_card.id)

    reflowed_users = []
    for user, partner_name in (
        (match_card.male_user, match_card.female_user.name),
        (match_card.female_user, match_card.male_user.name),
    ):
        user.is_in_match = False
        _append_emotional_history(user, partner_name, match_card)
        persist_user_status_change(
            user,
            actor,
            to_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            reason="配对卡结束自动回流",
            tag_editor=append_recommendation_tag,
            extra_update_fields=["is_in_match", "emotional_history"],
            before_json_extra={"is_in_match": True},
            after_json_extra={"is_in_match": False},
            timestamp=now,
        )
        reflowed_users.append(
            {
                "id": user.id,
                "name": user.name,
                "new_status": user.pool_status,
            }
        )

    create_operation_log(
        operator=actor,
        action="match_card_ended",
        target_type="match_card",
        target_id=match_card.id,
        before_json=before_json,
        after_json={
            "stage": match_card.stage,
            "ended_at": match_card.ended_at.isoformat(),
            "end_reason_staff": match_card.end_reason_staff,
        },
        reason=end_reason_staff,
    )
    return {
        "id": match_card.id,
        "stage": match_card.stage,
        "ended_at": match_card.ended_at,
        "message": "配对已结束，双方用户已回流未配对池",
        "reflowed_users": reflowed_users,
    }
