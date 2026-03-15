from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.staff.models import Staff


ACTIVE_MATCHCARD_STAGES = {
    MatchCard.STAGE_INITIAL_CONTACT,
    MatchCard.STAGE_STABLE_CONTACT,
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
}
REMIND_TYPE_MATCHED_REVISIT = "matched_revisit"
REMIND_TYPE_DISPLAY_MAP = {
    REMIND_TYPE_MATCHED_REVISIT: "已配对回访提醒",
}
STAGE_DISPLAY_MAP = {
    MatchCard.STAGE_INITIAL_CONTACT: "初期接触",
    MatchCard.STAGE_STABLE_CONTACT: "稳定联系",
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW: "成功待审核",
}
RISK_DISPLAY_MAP = {
    MatchCard.RISK_NONE: "无风险",
    MatchCard.RISK_WATCHING: "关注中",
    MatchCard.RISK_HIGH_RISK: "高风险",
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


def refresh_match_card_next_remind_at(match_card):
    reminders = build_match_card_reminders(match_card)
    next_remind_at = min((item["remind_at"] for item in reminders), default=None)
    match_card.next_remind_at = next_remind_at
    match_card.save(update_fields=["next_remind_at", "updated_at"])
    return next_remind_at


def _parse_datetime_query(value, field_name):
    if value in (None, ""):
        return None
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        raise ValidationError({field_name: [f"{field_name} 不是合法的 datetime。"]})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def build_reminder_list(actor, query_params):
    queryset = (
        MatchCard.objects.select_related(
            "male_user",
            "female_user",
            "male_staff",
            "female_staff",
            "primary_staff",
        )
        .filter(stage__in=ACTIVE_MATCHCARD_STAGES)
        .order_by("-created_at", "-id")
    )

    reminders = []
    for match_card in queryset:
        reminders.extend(build_match_card_reminders(match_card))

    if actor.role != Staff.ROLE_ADMIN:
        reminders = [item for item in reminders if item["staff_id"] == actor.id]
    else:
        staff_id = query_params.get("staff_id")
        if staff_id:
            try:
                staff_id_int = int(staff_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"staff_id": ["staff_id 必须为整数。"]}) from exc
            reminders = [item for item in reminders if item["staff_id"] == staff_id_int]

    status_filter = query_params.get("status")
    if status_filter:
        reminders = [item for item in reminders if item["status"] == status_filter]

    remind_type = query_params.get("remind_type")
    if remind_type:
        reminders = [item for item in reminders if item["remind_type"] == remind_type]

    target_type = query_params.get("target_type")
    if target_type:
        reminders = [item for item in reminders if item["target_type"] == target_type]

    remind_at_before = _parse_datetime_query(query_params.get("remind_at_before"), "remind_at_before")
    if remind_at_before is not None:
        reminders = [item for item in reminders if item["remind_at"] <= remind_at_before]

    remind_at_after = _parse_datetime_query(query_params.get("remind_at_after"), "remind_at_after")
    if remind_at_after is not None:
        reminders = [item for item in reminders if item["remind_at"] >= remind_at_after]

    reminders.sort(key=lambda item: (item["remind_at"], item["id"]))
    return reminders
