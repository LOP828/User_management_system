from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.oplog.services import create_operation_log
from apps.staff.models import Staff
from apps.user.models import CustomerProfile, UserStatusHistory


PROFILE_DETAIL_MIN_FIELDS = 10
POOL_STATUS_DISPLAY_MAP = {
    CustomerProfile.STATUS_NEW_PENDING: "新入库待处理",
    CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND: "已沟通待推荐",
    CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT: "已推荐待选择",
    CustomerProfile.STATUS_SELECTED_PENDING_MEET: "已选人待见面",
    CustomerProfile.STATUS_MET_NOT_CONTINUE: "已见面未继续",
    CustomerProfile.STATUS_PAUSED: "暂停服务",
}
ALLOWED_STATUS_TRANSITIONS = {
    CustomerProfile.STATUS_NEW_PENDING: {
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        CustomerProfile.STATUS_PAUSED,
    },
    CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND: {
        CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT,
        CustomerProfile.STATUS_PAUSED,
    },
    CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT: {
        CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        CustomerProfile.STATUS_PAUSED,
    },
    CustomerProfile.STATUS_SELECTED_PENDING_MEET: {
        CustomerProfile.STATUS_MET_NOT_CONTINUE,
        CustomerProfile.STATUS_PAUSED,
    },
    CustomerProfile.STATUS_MET_NOT_CONTINUE: {
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    },
}
PAUSABLE_STATUSES = {
    CustomerProfile.STATUS_NEW_PENDING,
    CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT,
    CustomerProfile.STATUS_SELECTED_PENDING_MEET,
}
OWNER_SYNC_MATCHCARD_STAGES = {
    MatchCard.STAGE_INITIAL_CONTACT,
    MatchCard.STAGE_STABLE_CONTACT,
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
}


def validate_minimum_contact(data):
    if any(data.get(field) for field in ("phone", "wechat", "other_contact")):
        return
    raise ValidationError(
        {
            "non_field_errors": [
                "phone、wechat、other_contact 至少填写一项。"
            ]
        }
    )


def validate_owner_for_actor(actor, owner):
    if owner.status != Staff.STATUS_ACTIVE or owner.role != Staff.ROLE_MATCHMAKER:
        raise ValidationError({"owner_id": ["负责人必须为有效且启用的红娘。"]})

    if actor.role == Staff.ROLE_MATCHMAKER and owner.id != actor.id:
        raise PermissionDenied("红娘只能创建或编辑自己负责的用户。")


def calculate_profile_complete(payload):
    profile_detail = payload.get("profile_detail")
    if not isinstance(profile_detail, dict):
        return False

    required_values = (
        payload.get("name"),
        payload.get("gender"),
        payload.get("age"),
        payload.get("city"),
        payload.get("payment_level"),
        payload.get("owner"),
        payload.get("basic_requirement"),
    )
    if not all(required_values):
        return False

    if not any(payload.get(field) for field in ("phone", "wechat", "other_contact")):
        return False

    return len(profile_detail) >= PROFILE_DETAIL_MIN_FIELDS


def can_view_user(actor, user):
    if actor.role == Staff.ROLE_ADMIN:
        return True
    if user.owner_id == actor.id:
        return True
    return MatchCard.objects.filter(
        Q(male_user_id=user.id) | Q(female_user_id=user.id)
    ).filter(
        Q(male_staff_id=actor.id) | Q(female_staff_id=actor.id) | Q(primary_staff_id=actor.id)
    ).exists()


def require_user_view_access(actor, user):
    if not can_view_user(actor, user):
        raise PermissionDenied("无权限")


def can_edit_user(actor, user):
    if actor.role == Staff.ROLE_ADMIN:
        return True
    return user.owner_id == actor.id


def require_user_edit_access(actor, user):
    if not can_edit_user(actor, user):
        raise PermissionDenied("无权限")


def create_initial_status_history(user, changed_by):
    create_status_history(
        user=user,
        changed_by=changed_by,
        from_status=None,
        to_status=user.pool_status,
    )


def create_status_history(user, changed_by, from_status, to_status, reason=None, reason_obj=None, reason_note=None):
    UserStatusHistory.objects.create(
        user=user,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        reason=reason,
        reason_id=reason_obj,
        reason_note=reason_note,
    )


def build_user_list_queryset(actor, queryset):
    if actor.role == Staff.ROLE_ADMIN:
        return queryset
    return queryset.filter(owner_id=actor.id)


def build_customer_payload(validated_data):
    payload = dict(validated_data)
    payload.setdefault("tags", [])
    return payload


def sync_owner_related_active_match_cards(user, new_owner):
    """Sync side staff on active match cards; derived reminder receivers follow these fields."""
    match_cards = MatchCard.objects.filter(
        stage__in=OWNER_SYNC_MATCHCARD_STAGES,
    ).filter(
        Q(male_user_id=user.id) | Q(female_user_id=user.id)
    )
    for match_card in match_cards:
        update_fields = []
        if match_card.male_user_id == user.id and match_card.male_staff_id != new_owner.id:
            match_card.male_staff = new_owner
            update_fields.append("male_staff")
        if match_card.female_user_id == user.id and match_card.female_staff_id != new_owner.id:
            match_card.female_staff = new_owner
            update_fields.append("female_staff")
        if update_fields:
            match_card.save(update_fields=[*update_fields, "updated_at"])


def create_customer_profile(validated_data, actor):
    payload = build_customer_payload(validated_data)
    validate_minimum_contact(payload)
    validate_owner_for_actor(actor, payload["owner"])
    payload["pool_status"] = CustomerProfile.STATUS_NEW_PENDING
    payload["is_profile_complete"] = calculate_profile_complete(payload)
    payload["is_in_match"] = False
    user = CustomerProfile.objects.create(**payload)
    user.last_unmatched_active_at = user.created_at
    user.save(update_fields=["last_unmatched_active_at", "updated_at"])
    create_initial_status_history(user, actor)
    return user


@transaction.atomic
def update_customer_profile(instance, validated_data, actor, force=False, force_reason=None):
    require_user_edit_access(actor, instance)

    if "owner" in validated_data:
        # BR-TRANSFER-003: 仅 admin 可直接修改 owner_id，需 force + force_reason
        if actor.role != Staff.ROLE_ADMIN:
            raise PermissionDenied("红娘不可修改 owner_id。")
        if not force:
            raise BusinessRuleError(
                "FORCE_REASON_REQUIRED",
                "修改负责人必须传 force=true",
                status.HTTP_400_BAD_REQUEST,
            )
        if not force_reason:
            raise BusinessRuleError(
                "FORCE_REASON_REQUIRED",
                "修改负责人必须填写 force_reason",
                status.HTTP_400_BAD_REQUEST,
            )

    payload = build_customer_payload(
        {
            "name": validated_data.get("name", instance.name),
            "gender": validated_data.get("gender", instance.gender),
            "age": validated_data.get("age", instance.age),
            "phone": validated_data.get("phone", instance.phone),
            "wechat": validated_data.get("wechat", instance.wechat),
            "other_contact": validated_data.get("other_contact", instance.other_contact),
            "city": validated_data.get("city", instance.city),
            "payment_level": validated_data.get("payment_level", instance.payment_level),
            "owner": validated_data.get("owner", instance.owner),
            "basic_requirement": validated_data.get("basic_requirement", instance.basic_requirement),
            "profile_detail": validated_data.get("profile_detail", instance.profile_detail),
            "tags": validated_data.get("tags", instance.tags),
        }
    )
    validate_minimum_contact(payload)
    validate_owner_for_actor(actor, payload["owner"])
    old_owner_id = instance.owner_id
    owner_changed = payload["owner"].id != old_owner_id
    if owner_changed:
        instance.last_action_at = timezone.now()

    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.is_profile_complete = calculate_profile_complete(payload)
    instance.save()

    if owner_changed:
        sync_owner_related_active_match_cards(instance, instance.owner)
        create_operation_log(
            operator=actor,
            action="admin_force_change",
            target_type="user",
            target_id=instance.id,
            before_json={"owner_id": old_owner_id},
            after_json={"owner_id": instance.owner_id},
            reason=force_reason,
        )

    return instance


def get_pool_status_display(pool_status):
    return POOL_STATUS_DISPLAY_MAP.get(pool_status, pool_status)


def assert_user_owner_or_admin(actor, user):
    if actor.role == Staff.ROLE_ADMIN:
        return
    if user.owner_id != actor.id:
        raise PermissionDenied("无权限")


def assert_target_status_valid(to_status):
    valid_statuses = {choice[0] for choice in CustomerProfile.POOL_STATUS_CHOICES}
    if to_status not in valid_statuses:
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "状态流转不合法",
            status.HTTP_400_BAD_REQUEST,
        )


def append_recommendation_tag(tags):
    normalized_tags = list(tags or [])
    if "待重新推荐" not in normalized_tags:
        normalized_tags.append("待重新推荐")
    return normalized_tags


def build_status_response(user, message, force_applied=False, include_pre_pause=False):
    response = {
        "id": user.id,
        "pool_status": user.pool_status,
        "pool_status_display": get_pool_status_display(user.pool_status),
        "message": message,
    }
    if include_pre_pause:
        response["pre_pause_status"] = user.pre_pause_status
    if force_applied is not None:
        response["force_applied"] = force_applied
    return response


def change_user_status(user, actor, to_status, reason="", force=False, force_reason=None):
    assert_user_owner_or_admin(actor, user)
    assert_target_status_valid(to_status)

    if force and actor.role != Staff.ROLE_ADMIN:
        raise PermissionDenied("无权限")
    if force and not force_reason:
        raise BusinessRuleError(
            "FORCE_REASON_REQUIRED",
            "管理员 force 操作必须填写 force_reason",
            status.HTTP_400_BAD_REQUEST,
        )
    if not force and user.pool_status == CustomerProfile.STATUS_PAUSED:
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "暂停状态请使用恢复接口",
            status.HTTP_400_BAD_REQUEST,
        )
    if not force and to_status == CustomerProfile.STATUS_PAUSED:
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "暂停请使用专用接口",
            status.HTTP_400_BAD_REQUEST,
        )
    if not force and to_status not in ALLOWED_STATUS_TRANSITIONS.get(user.pool_status, set()):
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "状态流转不合法",
            status.HTTP_400_BAD_REQUEST,
        )
    if (
        not force
        and user.pool_status == CustomerProfile.STATUS_MET_NOT_CONTINUE
        and to_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    ):
        # BR-POOL-002: 退出 met_not_continue 需要存在失败跟进记录
        entered_at = (
            UserStatusHistory.objects.filter(
                user=user,
                to_status=CustomerProfile.STATUS_MET_NOT_CONTINUE,
            )
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        qs = FollowUpRecord.objects.filter(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            failure_reason__isnull=False,
        )
        if entered_at is not None:
            qs = qs.filter(created_at__gt=entered_at)
        if not qs.exists():
            raise BusinessRuleError(
                "FAILURE_REASON_REQUIRED",
                "必须填写失败原因",
                status.HTTP_400_BAD_REQUEST,
            )

    now = timezone.now()
    before_json = {
        "pool_status": user.pool_status,
        "pre_pause_status": user.pre_pause_status,
        "tags": user.tags or [],
    }
    from_status = user.pool_status
    update_fields = ["pool_status", "last_action_at", "updated_at"]
    user.pool_status = to_status
    user.last_action_at = now

    # BR-REMIND-009: 未配对池内状态变更时更新超时基线
    if to_status != CustomerProfile.STATUS_PAUSED:
        user.last_unmatched_active_at = now
        update_fields.append("last_unmatched_active_at")

    if to_status == CustomerProfile.STATUS_PAUSED:
        user.pre_pause_status = from_status if from_status != CustomerProfile.STATUS_PAUSED else user.pre_pause_status
        if "pre_pause_status" not in update_fields:
            update_fields.append("pre_pause_status")
    elif from_status == CustomerProfile.STATUS_PAUSED and user.pre_pause_status is not None:
        user.pre_pause_status = None
        update_fields.append("pre_pause_status")

    if to_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND and from_status == CustomerProfile.STATUS_MET_NOT_CONTINUE:
        user.tags = append_recommendation_tag(user.tags)
        update_fields.append("tags")

    user.save(update_fields=list(dict.fromkeys(update_fields)))
    create_status_history(
        user=user,
        changed_by=actor,
        from_status=from_status,
        to_status=to_status,
        reason=reason or None,
        reason_note=force_reason if force else None,
    )
    create_operation_log(
        operator=actor,
        action="admin_force_change" if force else "user_status_changed",
        target_type="user",
        target_id=user.id,
        before_json=before_json,
        after_json={
            "pool_status": user.pool_status,
            "pre_pause_status": user.pre_pause_status,
            "tags": user.tags or [],
        },
        reason=force_reason if force else (reason or None),
    )
    return build_status_response(user, "状态变更成功", force_applied=force)


def pause_user(user, actor, reason_id=None, reason_note=None):
    assert_user_owner_or_admin(actor, user)

    if user.pool_status not in PAUSABLE_STATUSES:
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "当前状态不允许暂停",
            status.HTTP_400_BAD_REQUEST,
        )
    if reason_id is None:
        raise BusinessRuleError(
            "PAUSE_REASON_REQUIRED",
            "必须填写暂停原因",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        reason_obj = ReasonEnum.objects.get(
            id=reason_id,
            category=ReasonEnum.CATEGORY_PAUSE,
            is_active=True,
        )
    except ReasonEnum.DoesNotExist as exc:
        raise BusinessRuleError(
            "PAUSE_REASON_REQUIRED",
            "必须填写暂停原因",
            status.HTTP_400_BAD_REQUEST,
        ) from exc

    now = timezone.now()
    before_json = {
        "pool_status": user.pool_status,
        "pre_pause_status": user.pre_pause_status,
    }
    from_status = user.pool_status
    user.pre_pause_status = from_status
    user.pool_status = CustomerProfile.STATUS_PAUSED
    user.last_action_at = now
    user.save(update_fields=["pre_pause_status", "pool_status", "last_action_at", "updated_at"])
    create_status_history(
        user=user,
        changed_by=actor,
        from_status=from_status,
        to_status=CustomerProfile.STATUS_PAUSED,
        reason=reason_obj.label,
        reason_obj=reason_obj,
        reason_note=reason_note or None,
    )
    create_operation_log(
        operator=actor,
        action="user_status_changed",
        target_type="user",
        target_id=user.id,
        before_json=before_json,
        after_json={
            "pool_status": user.pool_status,
            "pre_pause_status": user.pre_pause_status,
        },
        reason=reason_note or reason_obj.label,
    )
    return build_status_response(user, "用户已暂停", force_applied=None, include_pre_pause=True)


def resume_user(user, actor):
    assert_user_owner_or_admin(actor, user)

    if user.pool_status != CustomerProfile.STATUS_PAUSED or not user.pre_pause_status:
        raise BusinessRuleError(
            "USER_STATUS_TRANSITION_INVALID",
            "当前状态不允许恢复",
            status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    before_json = {
        "pool_status": user.pool_status,
        "pre_pause_status": user.pre_pause_status,
    }
    from_status = user.pool_status
    to_status = user.pre_pause_status
    user.pool_status = to_status
    user.pre_pause_status = None
    user.last_action_at = now
    # BR-REMIND-009: 恢复到未配对池状态时更新超时基线
    user.last_unmatched_active_at = now
    user.save(update_fields=["pool_status", "pre_pause_status", "last_action_at", "last_unmatched_active_at", "updated_at"])
    create_status_history(
        user=user,
        changed_by=actor,
        from_status=from_status,
        to_status=to_status,
        reason="恢复服务",
        reason_note="恢复服务",
    )
    create_operation_log(
        operator=actor,
        action="user_status_changed",
        target_type="user",
        target_id=user.id,
        before_json=before_json,
        after_json={
            "pool_status": user.pool_status,
            "pre_pause_status": user.pre_pause_status,
        },
        reason="恢复服务",
    )
    return build_status_response(user, "用户已恢复", force_applied=None)
