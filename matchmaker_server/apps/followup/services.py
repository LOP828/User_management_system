from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.exceptions import BusinessRuleError
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.reminder.services import sync_match_card_revisit_reminders
from apps.staff.models import Staff


SUPPORTED_SCENES = {
    FollowUpRecord.SCENE_UNMATCHED,
    FollowUpRecord.SCENE_MATCHED,
    FollowUpRecord.SCENE_SUCCESS_FOLLOWUP,
}
UNMATCHED_REQUIRED_FIELDS = (
    "user",
    "content",
)
SUPPORTED_MATCHED_CARD_STAGES = {
    MatchCard.STAGE_INITIAL_CONTACT,
    MatchCard.STAGE_STABLE_CONTACT,
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
}
MATCHED_REQUIRED_FIELDS = (
    "match_card",
    "user",
    "content",
    "is_still_contact",
    "risk_status",
    "next_remind_mode",
)
SUCCESS_FOLLOWUP_REQUIRED_FIELDS = (
    "match_card",
    "content",
    "is_still_contact",
    "next_remind_mode",
)
FOLLOWUP_EDITABLE_FIELDS = {
    "content",
    "is_still_contact",
    "risk_status",
    "next_remind_mode",
    "next_remind_at",
}


def valid_matched_visit_q():
    return (
        Q(scene=FollowUpRecord.SCENE_MATCHED)
        & Q(user_id__isnull=False)
        & ~Q(content="")
        & Q(
            is_still_contact__in=[
                FollowUpRecord.CONTACT_YES,
                FollowUpRecord.CONTACT_NO,
                FollowUpRecord.CONTACT_UNKNOWN,
            ]
        )
        & Q(
            risk_status__in=[
                FollowUpRecord.RISK_NONE,
                FollowUpRecord.RISK_WATCHING,
                FollowUpRecord.RISK_HIGH_RISK,
            ]
        )
        & (
            (
                Q(next_remind_mode=FollowUpRecord.REMIND_MANUAL)
                & Q(next_remind_at__isnull=False)
            )
            | (
                Q(next_remind_mode=FollowUpRecord.REMIND_DEFAULT)
                & Q(next_remind_at__isnull=True)
            )
        )
    )


def is_valid_follow_up_record(follow_up):
    if follow_up.scene == FollowUpRecord.SCENE_MATCHED:
        if not follow_up.user_id or not follow_up.match_card_id or not follow_up.content:
            return False
        if follow_up.risk_status not in {
            FollowUpRecord.RISK_NONE,
            FollowUpRecord.RISK_WATCHING,
            FollowUpRecord.RISK_HIGH_RISK,
        }:
            return False
    elif follow_up.scene == FollowUpRecord.SCENE_SUCCESS_FOLLOWUP:
        if follow_up.user_id is not None or not follow_up.match_card_id or not follow_up.content:
            return False
    else:
        return False

    if follow_up.is_still_contact not in {
        FollowUpRecord.CONTACT_YES,
        FollowUpRecord.CONTACT_NO,
        FollowUpRecord.CONTACT_UNKNOWN,
    }:
        return False
    if follow_up.next_remind_mode == FollowUpRecord.REMIND_MANUAL:
        return follow_up.next_remind_at is not None
    if follow_up.next_remind_mode == FollowUpRecord.REMIND_DEFAULT:
        return follow_up.next_remind_at is None
    return False


def build_followup_queryset(actor, queryset):
    if actor.role == Staff.ROLE_ADMIN:
        return queryset
    return queryset.filter(
        Q(staff_id=actor.id)
        | Q(match_card__male_staff_id=actor.id)
        | Q(match_card__female_staff_id=actor.id)
        | Q(match_card__primary_staff_id=actor.id)
        | Q(user__owner_id=actor.id)
    ).distinct()


def require_followup_view_permission(actor, follow_up):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == follow_up.staff_id:
        return
    if follow_up.match_card_id and actor.id in {
        follow_up.match_card.male_staff_id,
        follow_up.match_card.female_staff_id,
        follow_up.match_card.primary_staff_id,
    }:
        return
    if follow_up.user_id and follow_up.user.owner_id == actor.id:
        return
    raise PermissionDenied("无权限")


def require_supported_scene(scene):
    if scene in SUPPORTED_SCENES:
        return
    raise BusinessRuleError(
        "FOLLOWUP_SCENE_NOT_SUPPORTED",
        "当前批次仅支持 unmatched / matched / success_followup 跟进",
        status.HTTP_400_BAD_REQUEST,
    )


def ensure_unmatched_followup_permission(actor, user):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == user.owner_id:
        return
    raise PermissionDenied("无权限")


def ensure_match_card_side_permission(actor, match_card, user_id):
    if user_id not in {match_card.male_user_id, match_card.female_user_id}:
        raise ValidationError({"user_id": ["user_id 必须属于该配对卡。"]})

    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == match_card.primary_staff_id:
        return
    if actor.id == match_card.male_staff_id and user_id == match_card.male_user_id:
        return
    if actor.id == match_card.female_staff_id and user_id == match_card.female_user_id:
        return
    raise PermissionDenied("无权限")


def ensure_success_followup_permission(actor, match_card):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if actor.id == match_card.primary_staff_id:
        return
    raise PermissionDenied("无权限")


def validate_followup_scene_payload(data, instance=None):
    scene = data.get("scene") if instance is None else instance.scene
    require_supported_scene(scene)

    match_card = data.get("match_card") if instance is None else instance.match_card
    user = data.get("user") if instance is None else instance.user
    content = data.get("content") if instance is None else instance.content
    is_still_contact = data.get("is_still_contact") if instance is None else instance.is_still_contact
    risk_status = data.get("risk_status") if instance is None else instance.risk_status
    next_remind_mode = data.get("next_remind_mode") if instance is None else instance.next_remind_mode
    next_remind_at = data.get("next_remind_at") if instance is None else instance.next_remind_at

    if scene == FollowUpRecord.SCENE_UNMATCHED:
        missing = {}
        for field in UNMATCHED_REQUIRED_FIELDS:
            value = locals()[field]
            if value in (None, ""):
                missing[field] = [f"{field} 为必填项。"]
        if missing:
            raise ValidationError(missing)

        if match_card is not None:
            raise ValidationError({"match_card_id": ["unmatched 场景不允许填写 match_card_id。"]})
        if next_remind_mode not in {None, "", FollowUpRecord.REMIND_MANUAL}:
            raise ValidationError({"next_remind_mode": ["unmatched 场景仅允许 manual 或不传。"]})
        if next_remind_mode in {None, ""} and next_remind_at is not None:
            raise ValidationError({"next_remind_mode": ["填写 next_remind_at 时，next_remind_mode 必须为 manual。"]})
        return

    if scene == FollowUpRecord.SCENE_MATCHED:
        missing = {}
        for field in MATCHED_REQUIRED_FIELDS:
            value = locals()[field]
            if value in (None, ""):
                missing[field] = [f"{field} 为必填项。"]
        if missing:
            raise ValidationError(missing)

        if next_remind_mode == FollowUpRecord.REMIND_MANUAL and next_remind_at is None:
            raise ValidationError({"next_remind_at": ["next_remind_mode=manual 时必须填写 next_remind_at。"]})
        if next_remind_mode == FollowUpRecord.REMIND_DEFAULT and next_remind_at is not None:
            raise ValidationError({"next_remind_at": ["next_remind_mode=default 时 next_remind_at 必须为空。"]})

        if match_card.stage not in SUPPORTED_MATCHED_CARD_STAGES:
            raise BusinessRuleError(
                "MATCH_STAGE_TRANSITION_INVALID",
                "当前配对卡阶段不支持保存 matched 回访",
                status.HTTP_400_BAD_REQUEST,
            )
        return

    missing = {}
    for field in SUCCESS_FOLLOWUP_REQUIRED_FIELDS:
        value = locals()[field]
        if value in (None, ""):
            missing[field] = [f"{field} 为必填项。"]
    if missing:
        raise ValidationError(missing)

    if user is not None:
        raise ValidationError({"user_id": ["success_followup 场景不允许填写 user_id。"]})
    if next_remind_mode == FollowUpRecord.REMIND_MANUAL and next_remind_at is None:
        raise ValidationError({"next_remind_at": ["next_remind_mode=manual 时必须填写 next_remind_at。"]})
    if next_remind_mode == FollowUpRecord.REMIND_DEFAULT and next_remind_at is not None:
        raise ValidationError({"next_remind_at": ["next_remind_mode=default 时 next_remind_at 必须为空。"]})
    if match_card.stage != MatchCard.STAGE_SUCCESS:
        raise BusinessRuleError(
            "MATCH_STAGE_TRANSITION_INVALID",
            "当前配对卡阶段不支持保存 success_followup 跟进",
            status.HTTP_400_BAD_REQUEST,
        )


def _refresh_match_card_last_visit_at(match_card):
    last_visit_at = (
        FollowUpRecord.objects.filter(match_card=match_card)
        .filter(valid_matched_visit_q())
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    match_card.last_visit_at = last_visit_at
    match_card.save(update_fields=["last_visit_at", "updated_at"])


def _touch_followup_user(user):
    user.last_action_at = timezone.now()
    user.save(update_fields=["last_action_at", "updated_at"])


def _touch_unmatched_user(user):
    now = timezone.now()
    user.last_action_at = now
    user.last_unmatched_active_at = now
    user.save(update_fields=["last_action_at", "last_unmatched_active_at", "updated_at"])


def _touch_match_card_users(match_card):
    now = timezone.now()
    match_card.male_user.last_action_at = now
    match_card.male_user.save(update_fields=["last_action_at", "updated_at"])
    match_card.female_user.last_action_at = now
    match_card.female_user.save(update_fields=["last_action_at", "updated_at"])


@transaction.atomic
def create_follow_up(validated_data, actor):
    require_supported_scene(validated_data["scene"])
    validate_followup_scene_payload(validated_data)

    scene = validated_data["scene"]
    match_card = validated_data.get("match_card")
    user = validated_data.get("user")
    if scene == FollowUpRecord.SCENE_UNMATCHED:
        ensure_unmatched_followup_permission(actor, user)
    elif scene == FollowUpRecord.SCENE_MATCHED:
        ensure_match_card_side_permission(actor, match_card, user.id)
    else:
        ensure_success_followup_permission(actor, match_card)

    follow_up = FollowUpRecord.objects.create(
        staff=actor,
        **validated_data,
    )
    if scene == FollowUpRecord.SCENE_UNMATCHED:
        _touch_unmatched_user(user)
    elif scene == FollowUpRecord.SCENE_MATCHED:
        _touch_followup_user(user)
    else:
        _touch_match_card_users(match_card)
    if scene == FollowUpRecord.SCENE_MATCHED and is_valid_follow_up_record(follow_up):
        _refresh_match_card_last_visit_at(match_card)
        sync_match_card_revisit_reminders(match_card)
    return follow_up


@transaction.atomic
def update_follow_up(instance, validated_data, actor):
    require_followup_view_permission(actor, instance)
    if instance.scene == FollowUpRecord.SCENE_UNMATCHED:
        ensure_unmatched_followup_permission(actor, instance.user)
    elif instance.scene == FollowUpRecord.SCENE_MATCHED:
        ensure_match_card_side_permission(actor, instance.match_card, instance.user_id)
    else:
        ensure_success_followup_permission(actor, instance.match_card)

    attempted_fields = {field for field, value in validated_data.items() if value is not None or field == "next_remind_at"}
    if not attempted_fields:
        raise ValidationError({"non_field_errors": ["至少传入一个可更新字段。"]})
    if not attempted_fields.issubset(FOLLOWUP_EDITABLE_FIELDS):
        raise ValidationError({"non_field_errors": ["包含当前批次不允许修改的字段。"]})

    for field, value in validated_data.items():
        if field in attempted_fields:
            setattr(instance, field, value)

    validate_followup_scene_payload({}, instance=instance)
    instance.save()
    if instance.scene == FollowUpRecord.SCENE_UNMATCHED:
        _touch_unmatched_user(instance.user)
    elif instance.scene == FollowUpRecord.SCENE_MATCHED:
        _touch_followup_user(instance.user)
    else:
        _touch_match_card_users(instance.match_card)
    if instance.scene == FollowUpRecord.SCENE_MATCHED and is_valid_follow_up_record(instance):
        _refresh_match_card_last_visit_at(instance.match_card)
        sync_match_card_revisit_reminders(instance.match_card)
    return instance


def build_match_card_followups(match_card):
    return (
        FollowUpRecord.objects.filter(match_card=match_card, scene=FollowUpRecord.SCENE_MATCHED)
        .select_related("staff")
        .order_by("-created_at", "-id")
    )


def build_success_case_followups(success_case):
    return (
        FollowUpRecord.objects.filter(
            match_card=success_case.match_card,
            scene=FollowUpRecord.SCENE_SUCCESS_FOLLOWUP,
        )
        .select_related("staff")
        .order_by("-created_at", "-id")
    )


def get_match_card_valid_visit_count(match_card):
    return FollowUpRecord.objects.filter(match_card=match_card).filter(valid_matched_visit_q()).count()


def get_match_card_side_valid_visit_counts(match_card):
    queryset = FollowUpRecord.objects.filter(match_card=match_card).filter(valid_matched_visit_q())
    male_count = queryset.filter(user_id=match_card.male_user_id).count()
    female_count = queryset.filter(user_id=match_card.female_user_id).count()
    return {
        "male": male_count,
        "female": female_count,
        "total": male_count + female_count,
    }
