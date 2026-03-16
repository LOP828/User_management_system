from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.matchcard.permissions import can_view_match_card
from apps.reminder.models import Reminder
from apps.staff.models import Staff
from apps.user.models import CustomerProfile


ACTIVE_MATCHCARD_STAGES = {
    MatchCard.STAGE_INITIAL_CONTACT,
    MatchCard.STAGE_STABLE_CONTACT,
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
}
ACTIVE_REMINDER_STATUSES = {
    Reminder.STATUS_PENDING,
    Reminder.STATUS_SENT,
}
MATCH_CARD_REVISIT_REMIND_TYPES = {
    Reminder.TYPE_MATCHED_REVISIT,
    Reminder.TYPE_MANUAL,
}
MATCH_CARD_REFRESH_REMIND_TYPES = {
    Reminder.TYPE_MATCHED_REVISIT,
    Reminder.TYPE_SUCCESS_REVISIT,
    Reminder.TYPE_MANUAL,
}
REMIND_TYPE_MATCHED_REVISIT = "matched_revisit"
REMIND_TYPE_DISPLAY_MAP = {
    Reminder.TYPE_NORMAL: "普通提醒",
    Reminder.TYPE_FIRST_MEET_PENDING: "未首见待推进",
    Reminder.TYPE_FIRST_MEET_DELAYED: "首见已延迟",
    Reminder.TYPE_FIRST_MEET_WARNING: "未首见预警",
    Reminder.TYPE_FIRST_MEET_OVERDUE: "未首见超时",
    Reminder.TYPE_FOLLOWUP_TIMEOUT: "跟进超时",
    Reminder.TYPE_PAUSE_REVISIT: "暂停回访",
    REMIND_TYPE_MATCHED_REVISIT: "已配对回访提醒",
    Reminder.TYPE_SUCCESS_REVISIT: "成功后回访提醒",
    Reminder.TYPE_URGENT: "紧急提醒",
    Reminder.TYPE_MANUAL: "手动提醒",
}
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
POOL_STATUS_DISPLAY_MAP = {
    CustomerProfile.STATUS_NEW_PENDING: "新分配待沟通",
    CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND: "已沟通待推荐",
    CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT: "已推荐待选择",
    CustomerProfile.STATUS_SELECTED_PENDING_MEET: "已选择待见面",
    CustomerProfile.STATUS_MET_NOT_CONTINUE: "见面未继续",
    CustomerProfile.STATUS_PAUSED: "暂停中",
}


def _valid_matched_followups(match_card):
    queryset = FollowUpRecord.objects.filter(
        match_card=match_card,
        scene=FollowUpRecord.SCENE_MATCHED,
        user_id__isnull=False,
    ).select_related("staff")
    valid_records = []
    for record in queryset.order_by("created_at", "id"):
        if not record.content:
            continue
        if record.is_still_contact not in {
            FollowUpRecord.CONTACT_YES,
            FollowUpRecord.CONTACT_NO,
            FollowUpRecord.CONTACT_UNKNOWN,
        }:
            continue
        if record.risk_status not in {
            FollowUpRecord.RISK_NONE,
            FollowUpRecord.RISK_WATCHING,
            FollowUpRecord.RISK_HIGH_RISK,
        }:
            continue
        if record.next_remind_mode == FollowUpRecord.REMIND_MANUAL and record.next_remind_at is None:
            continue
        if record.next_remind_mode == FollowUpRecord.REMIND_DEFAULT and record.next_remind_at is not None:
            continue
        if record.next_remind_mode not in {
            FollowUpRecord.REMIND_MANUAL,
            FollowUpRecord.REMIND_DEFAULT,
        }:
            continue
        valid_records.append(record)
    return valid_records


def _default_matched_remind_at(match_card, valid_records):
    if not valid_records:
        return match_card.created_at + timedelta(days=7), match_card.created_at

    valid_visit_count = len(valid_records)
    latest_valid = valid_records[-1]
    if valid_visit_count == 1:
        return match_card.created_at + timedelta(days=14), latest_valid.created_at
    if valid_visit_count == 2:
        return match_card.created_at + timedelta(days=30), latest_valid.created_at
    return latest_valid.created_at + timedelta(days=30), latest_valid.created_at


def _latest_side_valid_followup(valid_records, user_id):
    side_records = [record for record in valid_records if record.user_id == user_id]
    return side_records[-1] if side_records else None


def _build_match_card_side_reminder(match_card, side):
    valid_records = _valid_matched_followups(match_card)
    default_remind_at, generated_at = _default_matched_remind_at(match_card, valid_records)
    side_user = match_card.male_user if side == "male" else match_card.female_user
    side_staff = match_card.male_staff if side == "male" else match_card.female_staff
    latest_side_followup = _latest_side_valid_followup(valid_records, side_user.id)

    remind_at = default_remind_at
    created_at = generated_at
    is_manual = False
    if (
        latest_side_followup is not None
        and latest_side_followup.next_remind_mode == FollowUpRecord.REMIND_MANUAL
        and latest_side_followup.next_remind_at is not None
    ):
        remind_at = latest_side_followup.next_remind_at
        created_at = latest_side_followup.created_at
        is_manual = True

    overdue_days = max((timezone.now() - remind_at).days, 0) if remind_at <= timezone.now() else 0
    timing_summary = f"已逾期{overdue_days}天" if overdue_days > 0 else f"应回访时间 {timezone.localtime(remind_at).strftime('%Y-%m-%d %H:%M')}"

    return {
        "id": match_card.id * 10 + (1 if side == "male" else 2),
        "target_type": "match_card",
        "target_id": match_card.id,
        "target_name": f"{match_card.male_user.name} × {match_card.female_user.name}",
        "target_summary": (
            f"{'男方' if side == 'male' else '女方'}回访 | "
            f"{STAGE_DISPLAY_MAP.get(match_card.stage, match_card.stage)} | "
            f"{RISK_DISPLAY_MAP.get(match_card.risk_level, match_card.risk_level)} | "
            f"{timing_summary}"
        ),
        "staff_id": side_staff.id,
        "staff_name": side_staff.name,
        "remind_type": REMIND_TYPE_MATCHED_REVISIT,
        "remind_type_display": REMIND_TYPE_DISPLAY_MAP[REMIND_TYPE_MATCHED_REVISIT],
        "remind_at": remind_at,
        "status": "pending",
        "is_manual": is_manual,
        "created_at": created_at,
        "overdue_days": overdue_days,
    }


def build_match_card_reminders(match_card):
    if match_card.stage not in ACTIVE_MATCHCARD_STAGES:
        return []
    return [
        _build_match_card_side_reminder(match_card, "male"),
        _build_match_card_side_reminder(match_card, "female"),
    ]


def _build_derived_match_card_next_remind_at(match_card):
    reminders = build_match_card_reminders(match_card)
    return min((item["remind_at"] for item in reminders), default=None)


def _build_persisted_match_card_next_remind_at(match_card):
    queryset = Reminder.objects.filter(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        remind_type__in=MATCH_CARD_REFRESH_REMIND_TYPES,
    ).order_by("remind_at", "id")
    if not queryset.exists():
        return None, False
    next_remind_at = queryset.filter(status__in=ACTIVE_REMINDER_STATUSES).values_list("remind_at", flat=True).first()
    return next_remind_at, True


def refresh_match_card_next_remind_at(match_card):
    next_remind_at, has_persisted_reminders = _build_persisted_match_card_next_remind_at(match_card)
    if not has_persisted_reminders:
        next_remind_at = _build_derived_match_card_next_remind_at(match_card)
    match_card.next_remind_at = next_remind_at
    match_card.save(update_fields=["next_remind_at", "updated_at"])
    return next_remind_at


def sync_match_card_revisit_reminders(match_card):
    Reminder.objects.filter(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        remind_type__in=MATCH_CARD_REVISIT_REMIND_TYPES,
        status__in=ACTIVE_REMINDER_STATUSES,
    ).update(status=Reminder.STATUS_EXPIRED)

    for item in build_match_card_reminders(match_card):
        Reminder.objects.create(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=match_card.id,
            staff_id=item["staff_id"],
            remind_type=Reminder.TYPE_MANUAL if item["is_manual"] else Reminder.TYPE_MATCHED_REVISIT,
            remind_at=item["remind_at"],
            status=Reminder.STATUS_PENDING,
            is_manual=item["is_manual"],
        )

    return refresh_match_card_next_remind_at(match_card)


def _parse_datetime_query(value, field_name):
    if value in (None, ""):
        return None
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        raise ValidationError({field_name: [f"{field_name} 不是合法的 datetime。"]})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def build_persisted_reminder_queryset(actor, query_params):
    queryset = Reminder.objects.select_related("staff").order_by("remind_at", "id")

    if actor.role != Staff.ROLE_ADMIN:
        queryset = queryset.filter(staff_id=actor.id)
    else:
        staff_id = query_params.get("staff_id")
        if staff_id:
            try:
                staff_id_int = int(staff_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"staff_id": ["staff_id 必须为整数。"]}) from exc
            queryset = queryset.filter(staff_id=staff_id_int)

    status_filter = query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    remind_type = query_params.get("remind_type")
    if remind_type:
        queryset = queryset.filter(remind_type=remind_type)

    target_type = query_params.get("target_type")
    if target_type:
        queryset = queryset.filter(target_type=target_type)

    remind_at_before = _parse_datetime_query(query_params.get("remind_at_before"), "remind_at_before")
    if remind_at_before is not None:
        queryset = queryset.filter(remind_at__lte=remind_at_before)

    remind_at_after = _parse_datetime_query(query_params.get("remind_at_after"), "remind_at_after")
    if remind_at_after is not None:
        queryset = queryset.filter(remind_at__gte=remind_at_after)

    return queryset


def _get_user_target(target_id):
    try:
        return CustomerProfile.objects.select_related("payment_level", "owner").get(id=target_id, deleted_at__isnull=True)
    except CustomerProfile.DoesNotExist as exc:
        raise BusinessRuleError(
            "REMINDER_TARGET_NOT_FOUND",
            "提醒目标不存在",
            status.HTTP_400_BAD_REQUEST,
        ) from exc


def _get_match_card_target(target_id):
    try:
        return MatchCard.objects.select_related(
            "male_user",
            "female_user",
            "male_staff",
            "female_staff",
            "primary_staff",
        ).get(id=target_id)
    except MatchCard.DoesNotExist as exc:
        raise BusinessRuleError(
            "REMINDER_TARGET_NOT_FOUND",
            "提醒目标不存在",
            status.HTTP_400_BAD_REQUEST,
        ) from exc


def get_reminder_target(reminder):
    if reminder.target_type == Reminder.TARGET_USER:
        return _get_user_target(reminder.target_id)
    if reminder.target_type == Reminder.TARGET_MATCH_CARD:
        return _get_match_card_target(reminder.target_id)
    raise BusinessRuleError(
        "REMINDER_TARGET_TYPE_INVALID",
        "提醒目标类型不合法",
        status.HTTP_400_BAD_REQUEST,
    )


def _get_target_for_create(target_type, target_id):
    if target_type == Reminder.TARGET_USER:
        return _get_user_target(target_id)
    if target_type == Reminder.TARGET_MATCH_CARD:
        return _get_match_card_target(target_id)
    raise BusinessRuleError(
        "REMINDER_TARGET_TYPE_INVALID",
        "提醒目标类型不合法",
        status.HTTP_400_BAD_REQUEST,
    )


def create_reminder(*, target_type, target_id, staff, remind_type, remind_at, status_value=Reminder.STATUS_PENDING, is_manual=False):
    target = _get_target_for_create(target_type, target_id)
    reminder = Reminder.objects.create(
        target_type=target_type,
        target_id=target_id,
        staff=staff,
        remind_type=remind_type,
        remind_at=remind_at,
        status=status_value,
        is_manual=is_manual,
    )
    if target_type == Reminder.TARGET_MATCH_CARD:
        refresh_match_card_next_remind_at(target)
    return reminder


def _build_timing_summary(remind_at):
    if remind_at <= timezone.now():
        overdue_days = max((timezone.now() - remind_at).days, 0)
        return f"已逾期{overdue_days}天"
    return f"应处理时间 {timezone.localtime(remind_at).strftime('%Y-%m-%d %H:%M')}"


def build_reminder_display(reminder):
    target = get_reminder_target(reminder)
    remind_type_display = REMIND_TYPE_DISPLAY_MAP.get(reminder.remind_type, reminder.remind_type)
    timing_summary = _build_timing_summary(reminder.remind_at)

    if reminder.target_type == Reminder.TARGET_USER:
        payment_name = target.payment_level.name if target.payment_level_id else "-"
        return {
            "target_name": target.name,
            "target_summary": f"{POOL_STATUS_DISPLAY_MAP.get(target.pool_status, target.pool_status)} | {payment_name} | {timing_summary}",
            "remind_type_display": remind_type_display,
        }

    return {
        "target_name": f"{target.male_user.name} × {target.female_user.name}",
        "target_summary": (
            f"{remind_type_display} | "
            f"{STAGE_DISPLAY_MAP.get(target.stage, target.stage)} | "
            f"{RISK_DISPLAY_MAP.get(target.risk_level, target.risk_level)} | "
            f"{timing_summary}"
        ),
        "remind_type_display": remind_type_display,
    }


def _require_manual_user_reminder_permission(actor, user):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == user.owner_id:
        return
    raise PermissionDenied("无权限")


def _resolve_manual_match_card_staff(actor, match_card):
    if actor.role == Staff.ROLE_ADMIN:
        return match_card.primary_staff
    if can_view_match_card(actor, match_card):
        return actor
    raise PermissionDenied("无权限")


def _expire_manual_override_candidates(target_type, target_id, staff_id):
    queryset = Reminder.objects.filter(
        target_type=target_type,
        target_id=target_id,
        staff_id=staff_id,
        status__in=ACTIVE_REMINDER_STATUSES,
        is_manual=False,
    )
    updated = queryset.update(status=Reminder.STATUS_EXPIRED)
    if target_type == Reminder.TARGET_MATCH_CARD:
        refresh_match_card_next_remind_at(_get_match_card_target(target_id))
    return updated


def _expire_existing_manual_reminders(target_type, target_id, staff_id):
    queryset = Reminder.objects.filter(
        target_type=target_type,
        target_id=target_id,
        staff_id=staff_id,
        status__in=ACTIVE_REMINDER_STATUSES,
        is_manual=True,
    )
    updated = queryset.update(status=Reminder.STATUS_EXPIRED)
    if target_type == Reminder.TARGET_MATCH_CARD:
        refresh_match_card_next_remind_at(_get_match_card_target(target_id))
    return updated


def _resolve_manual_reminder_receiver(target_type, target, actor):
    if target_type == Reminder.TARGET_USER:
        _require_manual_user_reminder_permission(actor, target)
        return target.owner
    return _resolve_manual_match_card_staff(actor, target)


@transaction.atomic
def create_manual_reminder_for_target(*, target_type, target_id, remind_at, actor):
    target = _get_target_for_create(target_type, target_id)

    receiver = _resolve_manual_reminder_receiver(target_type, target, actor)

    _expire_manual_override_candidates(target_type, target_id, receiver.id)
    _expire_existing_manual_reminders(target_type, target_id, receiver.id)
    reminder = create_reminder(
        target_type=target_type,
        target_id=target_id,
        staff=receiver,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=remind_at,
        is_manual=True,
    )
    return reminder


@transaction.atomic
def create_manual_reminder(validated_data, actor):
    reminder = create_manual_reminder_for_target(
        target_type=validated_data["target_type"],
        target_id=validated_data["target_id"],
        remind_at=validated_data["remind_at"],
        actor=actor,
    )
    return {
        "id": reminder.id,
        "target_type": reminder.target_type,
        "target_id": reminder.target_id,
        "remind_type": reminder.remind_type,
        "remind_at": reminder.remind_at,
        "status": reminder.status,
        "is_manual": reminder.is_manual,
        "message": "手动提醒已设置，原有系统提醒已覆盖",
    }


def require_reminder_process_permission(actor, reminder):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if reminder.staff_id == actor.id:
        return
    raise PermissionDenied("无权限")


def _validate_overdue_reason(overdue_reason):
    if overdue_reason and overdue_reason.category == ReasonEnum.CATEGORY_OVERDUE and overdue_reason.is_active:
        return overdue_reason
    raise BusinessRuleError(
        "OVERDUE_REASON_REQUIRED",
        "处理未首见超时提醒必须填写有效的超时原因",
        status.HTTP_400_BAD_REQUEST,
    )


def _touch_user_after_reminder_processed(user, now, update_unmatched_baseline=False):
    user.last_action_at = now
    update_fields = ["last_action_at", "updated_at"]
    if update_unmatched_baseline:
        user.last_unmatched_active_at = now
        update_fields.append("last_unmatched_active_at")
    user.save(update_fields=update_fields)


def _touch_match_card_users_after_reminder_processed(match_card, now):
    match_card.male_user.last_action_at = now
    match_card.male_user.save(update_fields=["last_action_at", "updated_at"])
    match_card.female_user.last_action_at = now
    match_card.female_user.save(update_fields=["last_action_at", "updated_at"])


def _create_first_meet_overdue_follow_up(user, actor, overdue_reason, overdue_reason_note=None):
    return FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user,
        staff=actor,
        content="处理未首见超时提醒",
        overdue_reason=overdue_reason,
        overdue_reason_note=overdue_reason_note or None,
    )


@transaction.atomic
def process_reminder(reminder, actor, overdue_reason=None, overdue_reason_note=None):
    require_reminder_process_permission(actor, reminder)

    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        raise BusinessRuleError(
            "REMINDER_STATUS_TRANSITION_INVALID",
            "当前提醒状态不允许处理",
            status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    created_follow_up_id = None
    target = get_reminder_target(reminder)

    reminder.status = Reminder.STATUS_PROCESSED
    reminder.processed_at = now
    reminder.save(update_fields=["status", "processed_at"])

    if reminder.remind_type == Reminder.TYPE_FIRST_MEET_OVERDUE:
        overdue_reason = _validate_overdue_reason(overdue_reason)
        follow_up = _create_first_meet_overdue_follow_up(target, actor, overdue_reason, overdue_reason_note)
        created_follow_up_id = follow_up.id
        _touch_user_after_reminder_processed(target, now, update_unmatched_baseline=True)
    elif reminder.target_type == Reminder.TARGET_USER:
        _touch_user_after_reminder_processed(target, now)
    else:
        _touch_match_card_users_after_reminder_processed(target, now)
        refresh_match_card_next_remind_at(target)

    result = {
        "id": reminder.id,
        "status": reminder.status,
        "processed_at": reminder.processed_at,
    }
    if created_follow_up_id is not None:
        result["created_follow_up_id"] = created_follow_up_id
    return result


def expire_reminder(reminder):
    if reminder.status not in ACTIVE_REMINDER_STATUSES:
        return reminder

    reminder.status = Reminder.STATUS_EXPIRED
    reminder.save(update_fields=["status"])
    if reminder.target_type == Reminder.TARGET_MATCH_CARD:
        refresh_match_card_next_remind_at(get_reminder_target(reminder))
    return reminder


@transaction.atomic
def expire_target_reminders(target_type, target_id, remind_types=None):
    queryset = Reminder.objects.filter(
        target_type=target_type,
        target_id=target_id,
        status__in=ACTIVE_REMINDER_STATUSES,
    )
    if remind_types:
        queryset = queryset.filter(remind_type__in=remind_types)

    updated = queryset.update(status=Reminder.STATUS_EXPIRED)
    if target_type == Reminder.TARGET_MATCH_CARD:
        refresh_match_card_next_remind_at(_get_match_card_target(target_id))
    return updated
