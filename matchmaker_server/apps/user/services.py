from datetime import timedelta

from django.db import transaction
from django.db.models import Case, ExpressionWrapper, F, Func, IntegerField, Q, Value, When
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.oplog.services import (
    ACTION_ADMIN_FORCE_CHANGE,
    ACTION_USER_CREATED,
    ACTION_USER_OWNER_CHANGED,
    ACTION_USER_PAUSED,
    ACTION_USER_PROFILE_UPDATED,
    ACTION_USER_RESUMED,
    ACTION_USER_STATUS_CHANGED,
    create_operation_log,
)
from apps.reminder.models import Reminder
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
OWNER_SYNC_MATCHCARD_REMIND_TYPES = {
    Reminder.TYPE_MATCHED_REVISIT,
    Reminder.TYPE_MANUAL,
}


class _EpochSeconds(Func):
    """Extract epoch seconds from a datetime field. Works on both SQLite and PostgreSQL."""

    output_field = IntegerField()

    def as_sqlite(self, compiler, connection, **extra_context):
        lhs, params = compiler.compile(self.source_expressions[0])
        return f"CAST(strftime('%%s', {lhs}) AS INTEGER)", params

    def as_sql(self, compiler, connection, **extra_context):
        lhs, params = compiler.compile(self.source_expressions[0])
        return f"CAST(EXTRACT(EPOCH FROM {lhs}) AS INTEGER)", params


def annotate_priority_score(queryset):
    """BR-SORT-001/002: 在 QuerySet 上添加 priority_score annotation，支持 DB 层排序。

    score = homepage_weight + max(overdue_days, 0) * 10 + 新用户加分(15)
    当 overdue_days >= 7 时，保底 80 分。
    """
    now = timezone.now()
    now_epoch = int(now.timestamp())
    seven_days_ago = now - timedelta(days=7)

    return (
        queryset
        .annotate(
            _overdue_days=Case(
                When(
                    paid_at__isnull=False,
                    then=ExpressionWrapper(
                        (Value(now_epoch) - _EpochSeconds(F("paid_at"))) / Value(86400)
                        - F("payment_level__followup_timeout_days"),
                        output_field=IntegerField(),
                    ),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .annotate(
            _overdue_score=Case(
                When(_overdue_days__gt=0, then=F("_overdue_days") * Value(10)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            _new_bonus=Case(
                When(created_at__gte=seven_days_ago, then=Value(15)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .annotate(
            _base_score=ExpressionWrapper(
                F("payment_level__homepage_weight") + F("_overdue_score") + F("_new_bonus"),
                output_field=IntegerField(),
            ),
        )
        .annotate(
            priority_score=Case(
                When(_overdue_days__gte=7, then=Greatest(F("_base_score"), Value(80))),
                default=F("_base_score"),
                output_field=IntegerField(),
            ),
        )
    )


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


def persist_user_status_change(
    user,
    actor,
    *,
    to_status,
    reason=None,
    reason_obj=None,
    reason_note=None,
    action="user_status_changed",
    force=False,
    force_reason=None,
    tag_editor=None,
    update_last_unmatched=True,
    extra_update_fields=None,
    before_json_extra=None,
    after_json_extra=None,
    response_message=None,
    timestamp=None,
):
    now = timestamp or timezone.now()
    from_status = user.pool_status
    before_json = {
        "pool_status": from_status,
        "pre_pause_status": user.pre_pause_status,
        "tags": user.tags or [],
    }
    if before_json_extra:
        before_json.update(before_json_extra)

    user.pool_status = to_status
    user.last_action_at = now
    update_fields = ["pool_status", "last_action_at", "updated_at"]
    if update_last_unmatched and to_status != CustomerProfile.STATUS_PAUSED:
        user.last_unmatched_active_at = now
        update_fields.append("last_unmatched_active_at")
    if tag_editor:
        user.tags = tag_editor(user.tags)
        update_fields.append("tags")
    if extra_update_fields:
        update_fields.extend(extra_update_fields)

    user.save(update_fields=list(dict.fromkeys(update_fields)))
    create_status_history(
        user=user,
        changed_by=actor,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        reason_obj=reason_obj,
        reason_note=reason_note,
    )

    log_action = ACTION_ADMIN_FORCE_CHANGE if force else action
    log_reason = force_reason if force else (reason or None)
    after_json = {
        "pool_status": user.pool_status,
        "pre_pause_status": user.pre_pause_status,
        "tags": user.tags or [],
    }
    if after_json_extra:
        after_json.update(after_json_extra)

    create_operation_log(
        operator=actor,
        action=log_action,
        target_type="user",
        target_id=user.id,
        before_json=before_json,
        after_json=after_json,
        reason=log_reason,
    )

    if response_message is not None:
        return build_status_response(user, response_message, force_applied=force)


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


def sync_owner_related_pending_reminders(user, old_owner_id, new_owner):
    Reminder.objects.filter(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff_id=old_owner_id,
        status=Reminder.STATUS_PENDING,
    ).update(staff=new_owner)

    active_match_card_ids = list(
        MatchCard.objects.filter(stage__in=OWNER_SYNC_MATCHCARD_STAGES)
        .filter(Q(male_user_id=user.id) | Q(female_user_id=user.id))
        .values_list("id", flat=True)
    )
    if not active_match_card_ids:
        return

    Reminder.objects.filter(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id__in=active_match_card_ids,
        staff_id=old_owner_id,
        status=Reminder.STATUS_PENDING,
        remind_type__in=OWNER_SYNC_MATCHCARD_REMIND_TYPES,
    ).update(staff=new_owner)


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
    create_operation_log(
        operator=actor,
        action=ACTION_USER_CREATED,
        target_type="user",
        target_id=user.id,
        after_json={"pool_status": user.pool_status, "owner_id": user.owner_id},
    )
    return user


_VALIDATED_DATA_TO_DB_FIELD = {
    "owner": "owner_id",
    "payment_level": "payment_level_id",
}


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

    # 精确收集需要写入 DB 的字段，避免覆盖其他流程维护的字段
    update_fields = []
    for field, value in validated_data.items():
        setattr(instance, field, value)
        db_field = _VALIDATED_DATA_TO_DB_FIELD.get(field, field)
        update_fields.append(db_field)

    if owner_changed:
        instance.last_action_at = timezone.now()
        update_fields.append("last_action_at")

    instance.is_profile_complete = calculate_profile_complete(payload)
    update_fields.append("is_profile_complete")
    update_fields.append("updated_at")

    instance.save(update_fields=list(dict.fromkeys(update_fields)))

    if owner_changed:
        sync_owner_related_active_match_cards(instance, instance.owner)
        sync_owner_related_pending_reminders(instance, old_owner_id, instance.owner)
        create_operation_log(
            operator=actor,
            action=ACTION_USER_OWNER_CHANGED,
            target_type="user",
            target_id=instance.id,
            before_json={"owner_id": old_owner_id},
            after_json={"owner_id": instance.owner_id},
            reason=force_reason,
        )
    else:
        create_operation_log(
            operator=actor,
            action=ACTION_USER_PROFILE_UPDATED,
            target_type="user",
            target_id=instance.id,
            after_json={"is_profile_complete": instance.is_profile_complete},
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

    from_status = user.pool_status
    before_pre_pause = user.pre_pause_status
    extra_update_fields = []
    if to_status == CustomerProfile.STATUS_PAUSED:
        user.pre_pause_status = (
            from_status if from_status != CustomerProfile.STATUS_PAUSED else user.pre_pause_status
        )
        extra_update_fields.append("pre_pause_status")
        user.paused_at = timezone.now()
        extra_update_fields.append("paused_at")
    elif from_status == CustomerProfile.STATUS_PAUSED and user.pre_pause_status is not None:
        user.pre_pause_status = None
        extra_update_fields.append("pre_pause_status")
        user.paused_at = None
        extra_update_fields.append("paused_at")

    tag_editor = (
        append_recommendation_tag
        if from_status == CustomerProfile.STATUS_MET_NOT_CONTINUE
        and to_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
        else None
    )

    response = persist_user_status_change(
        user,
        actor,
        to_status=to_status,
        reason=reason or None,
        reason_note=force_reason if force else None,
        action="user_status_changed",
        force=force,
        force_reason=force_reason,
        tag_editor=tag_editor,
        extra_update_fields=extra_update_fields or None,
        before_json_extra={"pre_pause_status": before_pre_pause},
        response_message="状态变更成功",
    )
    if to_status == CustomerProfile.STATUS_MET_NOT_CONTINUE:
        from apps.recommendation.services import mark_selected_candidate_not_continue
        mark_selected_candidate_not_continue(user)
    return response


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
    user.paused_at = now
    user.save(update_fields=["pre_pause_status", "pool_status", "last_action_at", "paused_at", "updated_at"])
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
        action=ACTION_USER_PAUSED,
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
    user.paused_at = None
    user.last_action_at = now
    # BR-REMIND-009: 恢复到未配对池状态时更新超时基线
    user.last_unmatched_active_at = now
    user.save(update_fields=["pool_status", "pre_pause_status", "paused_at", "last_action_at", "last_unmatched_active_at", "updated_at"])
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
        action=ACTION_USER_RESUMED,
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
