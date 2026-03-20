from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import BusinessRuleError
from apps.matchcard.models import MatchCard
from apps.oplog.services import (
    ACTION_TRANSFER_APPLIED,
    ACTION_TRANSFER_APPROVED,
    ACTION_TRANSFER_REJECTED,
    ACTION_USER_OWNER_CHANGED,
    create_operation_log,
)
from apps.staff.models import Staff
from apps.transfer.models import UserTransferRequest
from apps.user.models import CustomerProfile
from apps.user.services import OWNER_SYNC_MATCHCARD_STAGES, sync_owner_related_pending_reminders


def _enqueue_transfer_applied_notification(transfer_request_id):
    from apps.notify.services import EVENT_TRANSFER_APPLIED, enqueue_phase1_event_safely
    from apps.notify.tasks import send_phase1_event

    transaction.on_commit(
        lambda: enqueue_phase1_event_safely(
            send_phase1_event,
            EVENT_TRANSFER_APPLIED,
            transfer_request_id,
        )
    )


def _sync_match_cards_and_capture(user, new_owner):
    """
    Sync active match card side staff fields for the given user.
    Returns a list of change dicts for the API response (affected_match_cards).
    Replaces direct call to sync_owner_related_active_match_cards so we can
    capture what changed without a second query.
    """
    match_cards = MatchCard.objects.filter(stage__in=OWNER_SYNC_MATCHCARD_STAGES).filter(
        Q(male_user_id=user.id) | Q(female_user_id=user.id)
    )
    affected = []
    for mc in match_cards:
        update_fields = []
        if mc.male_user_id == user.id and mc.male_staff_id != new_owner.id:
            mc.male_staff = new_owner
            update_fields.append("male_staff")
            affected.append({"id": mc.id, "updated_field": "male_staff_id", "new_staff_name": new_owner.name})
        if mc.female_user_id == user.id and mc.female_staff_id != new_owner.id:
            mc.female_staff = new_owner
            update_fields.append("female_staff")
            affected.append({"id": mc.id, "updated_field": "female_staff_id", "new_staff_name": new_owner.name})
        if update_fields:
            mc.save(update_fields=[*update_fields, "updated_at"])
    return affected


@transaction.atomic
def create_transfer_request(*, actor, user_id, to_staff_id, reason):
    """
    BR-TRANSFER-001 校验：
    1. matchmaker 只能为自己负责的用户发起
    2. to_staff 必须为有效启用的红娘
    3. from_staff != to_staff
    4. 同一用户不能有多个 pending 申请
    5. reason 非空（serializer 层已校验）
    """
    try:
        user = CustomerProfile.objects.select_related("owner").get(id=user_id)
    except CustomerProfile.DoesNotExist:
        raise BusinessRuleError("USER_NOT_FOUND", "用户不存在", 404)

    # 权限：matchmaker 只能转移自己负责的用户
    if actor.role == Staff.ROLE_MATCHMAKER and user.owner_id != actor.id:
        raise PermissionDenied("无权限：只能转移自己负责的用户")

    # BR-TRANSFER-001.3: from_staff != to_staff
    if user.owner_id == to_staff_id:
        raise BusinessRuleError("TRANSFER_SAME_STAFF", "目标红娘与当前负责人相同，无需转移")

    # BR-TRANSFER-001.2: to_staff 必须为有效启用的红娘
    try:
        to_staff = Staff.objects.get(id=to_staff_id)
    except Staff.DoesNotExist:
        raise BusinessRuleError("TO_STAFF_NOT_FOUND", "目标红娘不存在", 404)
    if to_staff.status != Staff.STATUS_ACTIVE or to_staff.role != Staff.ROLE_MATCHMAKER:
        raise BusinessRuleError("TO_STAFF_INVALID", "目标红娘必须为有效且启用的红娘")

    # BR-TRANSFER-001.4: 同一用户不能有多个 pending 申请
    if UserTransferRequest.objects.filter(user_id=user_id, status=UserTransferRequest.STATUS_PENDING).exists():
        raise BusinessRuleError("TRANSFER_PENDING_EXISTS", "该用户已有待审批的转移申请")

    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=user.owner,
        to_staff=to_staff,
        reason=reason,
    )

    create_operation_log(
        operator=actor,
        action=ACTION_TRANSFER_APPLIED,
        target_type="user_transfer_request",
        target_id=req.id,
        after_json={"from_staff_id": user.owner_id, "to_staff_id": to_staff_id},
    )
    _enqueue_transfer_applied_notification(req.id)

    return req


@transaction.atomic
def approve_transfer_request(*, actor, transfer_id):
    """
    BR-TRANSFER-002 审批通过：
    1. status → approved
    2. user.owner_id → to_staff_id
    3. 同步进行中配对卡的侧边 staff 字段
    4. 同步该用户 pending 提醒的接收人
    5. user.last_action_at = now
    6. 写操作日志
    """
    if actor.role != Staff.ROLE_ADMIN:
        raise PermissionDenied("仅管理员可审批转移申请")

    try:
        req = UserTransferRequest.objects.select_related("user__owner", "to_staff").get(id=transfer_id)
    except UserTransferRequest.DoesNotExist:
        raise BusinessRuleError("TRANSFER_NOT_FOUND", "转移申请不存在", 404)

    if req.status != UserTransferRequest.STATUS_PENDING:
        raise BusinessRuleError("TRANSFER_NOT_PENDING", "该申请已审批，不可重复操作")

    now = timezone.now()
    req.status = UserTransferRequest.STATUS_APPROVED
    req.reviewer = actor
    req.reviewed_at = now
    req.save(update_fields=["status", "reviewer", "reviewed_at"])

    user = req.user
    old_owner_id = user.owner_id
    new_owner = req.to_staff

    user.owner = new_owner
    user.last_action_at = now
    user.save(update_fields=["owner", "last_action_at", "updated_at"])

    affected = _sync_match_cards_and_capture(user, new_owner)
    sync_owner_related_pending_reminders(user, old_owner_id, new_owner)

    create_operation_log(
        operator=actor,
        action=ACTION_TRANSFER_APPROVED,
        target_type="user_transfer_request",
        target_id=req.id,
        before_json={"owner_id": old_owner_id},
        after_json={"owner_id": new_owner.id, "status": "approved"},
    )
    create_operation_log(
        operator=actor,
        action=ACTION_USER_OWNER_CHANGED,
        target_type="user",
        target_id=user.id,
        before_json={"owner_id": old_owner_id},
        after_json={"owner_id": new_owner.id},
    )

    return req, affected


@transaction.atomic
def reject_transfer_request(*, actor, transfer_id, review_note=""):
    """
    驳回转移申请：status → rejected，仅 admin 可操作。
    """
    if actor.role != Staff.ROLE_ADMIN:
        raise PermissionDenied("仅管理员可驳回转移申请")

    try:
        req = UserTransferRequest.objects.get(id=transfer_id)
    except UserTransferRequest.DoesNotExist:
        raise BusinessRuleError("TRANSFER_NOT_FOUND", "转移申请不存在", 404)

    if req.status != UserTransferRequest.STATUS_PENDING:
        raise BusinessRuleError("TRANSFER_NOT_PENDING", "该申请已审批，不可重复操作")

    now = timezone.now()
    req.status = UserTransferRequest.STATUS_REJECTED
    req.reviewer = actor
    req.review_note = review_note
    req.reviewed_at = now
    req.save(update_fields=["status", "reviewer", "review_note", "reviewed_at"])

    create_operation_log(
        operator=actor,
        action=ACTION_TRANSFER_REJECTED,
        target_type="user_transfer_request",
        target_id=req.id,
        after_json={"status": "rejected", "review_note": review_note},
    )

    return req
