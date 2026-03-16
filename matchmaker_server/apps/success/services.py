from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import BusinessRuleError
from apps.followup.services import get_match_card_side_valid_visit_counts
from apps.matchcard.models import MatchCard
from apps.matchcard.permissions import can_view_match_card
from apps.oplog.services import create_operation_log
from apps.reminder.models import Reminder
from apps.reminder.services import create_reminder, expire_target_reminders
from apps.staff.models import Staff
from apps.success.models import SuccessApplication, SuccessCase


def build_success_application_queryset(actor, queryset):
    if actor.role == Staff.ROLE_ADMIN:
        return queryset
    return queryset.filter(applicant_id=actor.id)


def build_success_case_queryset(actor, queryset):
    if actor.role == Staff.ROLE_ADMIN:
        return queryset
    return queryset.filter(
        Q(match_card__male_staff_id=actor.id)
        | Q(match_card__female_staff_id=actor.id)
        | Q(match_card__primary_staff_id=actor.id)
    )


def _require_applicant_permission(actor, match_card):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == match_card.primary_staff_id:
        return
    raise PermissionDenied("无权限")


def _require_admin(actor):
    if actor.role != Staff.ROLE_ADMIN:
        raise PermissionDenied("无权限")


def _require_success_case_view_permission(actor, success_case):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if can_view_match_card(actor, success_case.match_card):
        return
    raise PermissionDenied("无权限")


def _require_success_case_invalidate_permission(actor, success_case):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == success_case.match_card.primary_staff_id:
        return
    raise PermissionDenied("无权限")


def _ensure_pending_application(application):
    if application.status != SuccessApplication.STATUS_PENDING:
        raise BusinessRuleError(
            "SUCCESS_APPLICATION_ALREADY_REVIEWED",
            "成功申请已处理",
            status.HTTP_400_BAD_REQUEST,
        )


def _ensure_success_application_prerequisites(match_card):
    if match_card.stage != MatchCard.STAGE_STABLE_CONTACT:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "当前阶段不允许发起成功申请，配对卡须处于稳定联系阶段",
            status.HTTP_400_BAD_REQUEST,
        )

    valid_visit_counts = get_match_card_side_valid_visit_counts(match_card)
    if valid_visit_counts["male"] < 2 or valid_visit_counts["female"] < 2:
        raise BusinessRuleError(
            "MATCH_NOT_ENOUGH_VISITS",
            "男女双方各至少需要 2 条有效回访",
            status.HTTP_400_BAD_REQUEST,
        )

    if not (match_card.staff_judgment or "").strip():
        raise BusinessRuleError(
            "MATCH_RELATIONSHIP_NOT_CONFIRMED",
            "请先在配对卡填写红娘综合判断，确认双方恋爱关系",
            status.HTTP_400_BAD_REQUEST,
        )

    age_days = (timezone.now() - match_card.created_at).days
    if age_days < 30:
        raise BusinessRuleError(
            "MATCH_DURATION_TOO_SHORT",
            "配对卡存续时间不足30天",
            status.HTTP_400_BAD_REQUEST,
        )


def _create_success_revisit_reminders(match_card, approved_at):
    for days in (30, 90, 180):
        create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=match_card.id,
            staff=match_card.primary_staff,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            remind_at=approved_at + timedelta(days=days),
        )


@transaction.atomic
def create_success_application(validated_data, actor):
    """BR-SUCCESS-001: 前置条件 stage=stable_contact，创建后推进到 success_pending_review。"""
    match_card = validated_data["match_card"]
    _require_applicant_permission(actor, match_card)
    _ensure_success_application_prerequisites(match_card)

    if SuccessApplication.objects.filter(
        match_card=match_card,
        status=SuccessApplication.STATUS_PENDING,
    ).exists():
        raise BusinessRuleError(
            "SUCCESS_PENDING_EXISTS",
            "已有待审批的成功申请",
            status.HTTP_400_BAD_REQUEST,
        )

    application = SuccessApplication.objects.create(
        match_card=match_card,
        applicant=actor,
        apply_note=validated_data.get("apply_note"),
        status=SuccessApplication.STATUS_PENDING,
    )

    # PRD §16.2: 发起成功申请后，配对卡阶段推进到"成功待审核"
    old_stage = match_card.stage
    match_card.stage = MatchCard.STAGE_SUCCESS_PENDING_REVIEW
    match_card.save(update_fields=["stage", "updated_at"])

    create_operation_log(
        operator=actor,
        action="success_applied",
        target_type="match_card",
        target_id=match_card.id,
        before_json={"match_card_stage": old_stage},
        after_json={
            "success_application_id": application.id,
            "status": application.status,
            "match_card_stage": match_card.stage,
        },
        reason=application.apply_note or None,
    )
    return application


@transaction.atomic
def approve_success_application(application, actor):
    _require_admin(actor)
    _ensure_pending_application(application)

    now = timezone.now()
    application.status = SuccessApplication.STATUS_APPROVED
    application.reviewer = actor
    application.reviewed_at = now
    application.review_note = None
    application.save(update_fields=["status", "reviewer", "reviewed_at", "review_note"])

    success_case = SuccessCase.objects.create(
        match_card=application.match_card,
        application=application,
        status=SuccessCase.STATUS_ACTIVE,
        approved_at=now,
    )

    match_card = application.match_card
    match_card.stage = MatchCard.STAGE_SUCCESS
    match_card.next_remind_at = None
    match_card.save(update_fields=["stage", "next_remind_at", "updated_at"])
    _create_success_revisit_reminders(match_card, now)

    match_card.male_user.is_in_match = False
    match_card.male_user.save(update_fields=["is_in_match", "updated_at"])
    match_card.female_user.is_in_match = False
    match_card.female_user.save(update_fields=["is_in_match", "updated_at"])

    create_operation_log(
        operator=actor,
        action="success_approved",
        target_type="success_case",
        target_id=success_case.id,
        before_json={"application_status": SuccessApplication.STATUS_PENDING, "match_card_stage": MatchCard.STAGE_SUCCESS_PENDING_REVIEW},
        after_json={
            "application_status": application.status,
            "match_card_stage": match_card.stage,
            "success_case_status": success_case.status,
        },
        reason=None,
    )

    return {
        "id": application.id,
        "status": application.status,
        "reviewed_at": application.reviewed_at,
        "success_case_id": success_case.id,
        "message": "成功案例已入库",
    }


@transaction.atomic
def reject_success_application(application, actor, review_note):
    _require_admin(actor)
    _ensure_pending_application(application)

    now = timezone.now()
    application.status = SuccessApplication.STATUS_REJECTED
    application.reviewer = actor
    application.reviewed_at = now
    application.review_note = review_note
    application.save(update_fields=["status", "reviewer", "reviewed_at", "review_note"])

    match_card = application.match_card
    match_card.stage = MatchCard.STAGE_STABLE_CONTACT
    match_card.save(update_fields=["stage", "updated_at"])

    create_operation_log(
        operator=actor,
        action="success_rejected",
        target_type="match_card",
        target_id=match_card.id,
        before_json={"application_status": SuccessApplication.STATUS_PENDING, "match_card_stage": MatchCard.STAGE_SUCCESS_PENDING_REVIEW},
        after_json={
            "application_status": application.status,
            "match_card_stage": match_card.stage,
        },
        reason=review_note,
    )

    return {
        "id": application.id,
        "status": application.status,
        "review_note": application.review_note,
        "reviewed_at": application.reviewed_at,
        "message": "已驳回，配对卡已回退到稳定联系",
    }


@transaction.atomic
def invalidate_success_case(success_case, actor, reason_id, reason_note=None):
    _require_success_case_invalidate_permission(actor, success_case)

    if success_case.status != SuccessCase.STATUS_ACTIVE:
        raise BusinessRuleError(
            "SUCCESS_CASE_ALREADY_INVALIDATED",
            "成功案例已失效",
            status.HTTP_400_BAD_REQUEST,
        )
    if success_case.match_card.stage != MatchCard.STAGE_SUCCESS:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "当前配对卡阶段不允许标记成功失效",
            status.HTTP_400_BAD_REQUEST,
        )
    if reason_id.category != "success_invalidate" or not reason_id.is_active:
        raise BusinessRuleError(
            "SUCCESS_INVALIDATE_REASON_REQUIRED",
            "必须填写有效的成功失效原因",
            status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    success_case.status = SuccessCase.STATUS_INVALIDATED
    success_case.invalidated_reason = reason_id
    success_case.invalidated_reason_note = reason_note or None
    success_case.invalidated_at = now
    success_case.save(
        update_fields=[
            "status",
            "invalidated_reason",
            "invalidated_reason_note",
            "invalidated_at",
            "updated_at",
        ]
    )

    match_card = success_case.match_card
    match_card.stage = MatchCard.STAGE_ENDED
    match_card.ended_at = now
    match_card.next_remind_at = None
    match_card.save(update_fields=["stage", "ended_at", "next_remind_at", "updated_at"])
    expire_target_reminders(
        Reminder.TARGET_MATCH_CARD,
        match_card.id,
        remind_types=[Reminder.TYPE_SUCCESS_REVISIT],
    )

    match_card.male_user.is_in_match = False
    match_card.male_user.save(update_fields=["is_in_match", "updated_at"])
    match_card.female_user.is_in_match = False
    match_card.female_user.save(update_fields=["is_in_match", "updated_at"])

    create_operation_log(
        operator=actor,
        action="success_invalidated",
        target_type="success_case",
        target_id=success_case.id,
        before_json={
            "success_case_status": SuccessCase.STATUS_ACTIVE,
            "match_card_stage": MatchCard.STAGE_SUCCESS,
        },
        after_json={
            "success_case_status": success_case.status,
            "match_card_stage": match_card.stage,
            "invalidated_reason_id": success_case.invalidated_reason_id,
        },
        reason=reason_note or success_case.invalidated_reason.label,
    )

    return {
        "id": success_case.id,
        "status": success_case.status,
        "invalidated_at": success_case.invalidated_at,
        "message": "成功案例已标记失效，配对卡已结束",
    }
