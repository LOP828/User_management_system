"""
操作日志 action 命名收口测试
验证关键业务动作的日志是否落库、action 名称是否符合文档规范。
"""
import pytest
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.oplog.models import OperationLog
from apps.oplog.services import (
    ACTION_CANDIDATE_SELECTED,
    ACTION_FOLLOW_UP_CREATED,
    ACTION_FOLLOW_UP_UPDATED,
    ACTION_RECOMMENDATION_BATCH_CLOSED,
    ACTION_RECOMMENDATION_CREATED,
    ACTION_REMINDER_SET,
    ACTION_TRANSFER_APPLIED,
    ACTION_TRANSFER_APPROVED,
    ACTION_TRANSFER_REJECTED,
    ACTION_USER_CREATED,
    ACTION_USER_OWNER_CHANGED,
    ACTION_USER_PAUSED,
    ACTION_USER_PROFILE_UPDATED,
    ACTION_USER_RESUMED,
)
from apps.config_mgmt.models import ReasonEnum
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.reminder.models import Reminder
from apps.staff.models import Staff
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# 用户模块
# ---------------------------------------------------------------------------

def test_create_customer_profile_writes_user_created_log(
    matchmaker_staff, create_payment_level
):
    """创建用户（服务层）后应落 user_created 日志。"""
    from apps.user.services import create_customer_profile as create_user_svc
    payment_level = create_payment_level()
    validated_data = {
        "name": "日志测试用户",
        "gender": CustomerProfile.GENDER_MALE,
        "age": 28,
        "phone": "13900000001",
        "owner": matchmaker_staff,
        "payment_level": payment_level,
    }
    user = create_user_svc(validated_data, matchmaker_staff)
    log = OperationLog.objects.filter(
        action=ACTION_USER_CREATED, target_type="user", target_id=user.id
    ).first()
    assert log is not None
    assert log.after_json["owner_id"] == matchmaker_staff.id


def test_update_customer_profile_writes_user_profile_updated_log(
    auth_client, matchmaker_staff, create_customer_profile
):
    """更新用户资料（非 owner 变更）后应落 user_profile_updated 日志。"""
    user = create_customer_profile(owner=matchmaker_staff, name="资料更新前")
    resp = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"name": "资料更新后"},
        format="json",
    )
    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        action=ACTION_USER_PROFILE_UPDATED, target_type="user", target_id=user.id
    ).first()
    assert log is not None


def test_pause_user_writes_user_paused_log(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """暂停用户后应落 user_paused 日志，而非 user_status_changed。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE if hasattr(ReasonEnum, "CATEGORY_PAUSE") else "pause")
    resp = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/pause/",
        {"reason_id": reason.id},
        format="json",
    )
    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        action=ACTION_USER_PAUSED, target_type="user", target_id=user.id
    ).first()
    assert log is not None


def test_resume_user_writes_user_resumed_log(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """恢复用户后应落 user_resumed 日志，而非 user_status_changed。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_PAUSED,
    )
    user.pre_pause_status = CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    user.save(update_fields=["pre_pause_status", "updated_at"])
    resp = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/resume/",
        {},
        format="json",
    )
    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        action=ACTION_USER_RESUMED, target_type="user", target_id=user.id
    ).first()
    assert log is not None


# ---------------------------------------------------------------------------
# 跟进记录
# ---------------------------------------------------------------------------

def test_create_follow_up_writes_follow_up_created_log(
    auth_client, matchmaker_staff, create_customer_profile
):
    """创建 unmatched 跟进后应落 follow_up_created 日志。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )
    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": FollowUpRecord.SCENE_UNMATCHED,
            "user_id": user.id,
            "content": "已联系确认状态",
        },
        format="json",
    )
    assert resp.status_code == 201
    follow_up_id = resp.data["id"]
    log = OperationLog.objects.filter(
        action=ACTION_FOLLOW_UP_CREATED, target_type="follow_up", target_id=follow_up_id
    ).first()
    assert log is not None
    assert log.after_json["scene"] == FollowUpRecord.SCENE_UNMATCHED


def test_update_follow_up_writes_follow_up_updated_log(
    auth_client, matchmaker_staff, create_customer_profile
):
    """更新跟进记录后应落 follow_up_updated 日志。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )
    create_resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": FollowUpRecord.SCENE_UNMATCHED,
            "user_id": user.id,
            "content": "初始内容",
        },
        format="json",
    )
    assert create_resp.status_code == 201
    follow_up_id = create_resp.data["id"]

    patch_resp = auth_client(matchmaker_staff).patch(
        f"/api/v1/follow-ups/{follow_up_id}/",
        {"content": "更新后内容"},
        format="json",
    )
    assert patch_resp.status_code == 200
    log = OperationLog.objects.filter(
        action=ACTION_FOLLOW_UP_UPDATED, target_type="follow_up", target_id=follow_up_id
    ).first()
    assert log is not None


# ---------------------------------------------------------------------------
# 提醒
# ---------------------------------------------------------------------------

def test_set_manual_reminder_writes_reminder_set_log(
    auth_client, matchmaker_staff, create_customer_profile
):
    """通过 API 设置手动提醒后应落 reminder_set 日志。"""
    user = create_customer_profile(owner=matchmaker_staff)
    remind_at = (timezone.now() + timezone.timedelta(days=3)).isoformat()
    resp = auth_client(matchmaker_staff).post(
        "/api/v1/reminders/manual/",
        {
            "target_type": Reminder.TARGET_USER,
            "target_id": user.id,
            "remind_at": remind_at,
        },
        format="json",
    )
    assert resp.status_code == 201
    log = OperationLog.objects.filter(
        action=ACTION_REMINDER_SET, target_type=Reminder.TARGET_USER, target_id=user.id
    ).first()
    assert log is not None
    assert log.after_json["remind_type"] == Reminder.TYPE_MANUAL


# ---------------------------------------------------------------------------
# 推荐批次
# ---------------------------------------------------------------------------

def test_create_recommendation_batch_action_name(
    auth_client, matchmaker_staff, create_customer_profile, create_staff, create_payment_level
):
    """创建推荐批次日志 action 应为 recommendation_created（非旧 create_recommendation_batch）。"""
    payment_level = create_payment_level(recommend_limit=3)
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        payment_level=payment_level,
    )
    candidate_staff = create_staff(name="候选人红娘rec")
    candidate = create_customer_profile(owner=candidate_staff, gender=CustomerProfile.GENDER_FEMALE)

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/recommendations/",
        {"user_id": user.id, "candidate_user_ids": [candidate.id]},
        format="json",
    )
    assert resp.status_code == 201
    batch_id = resp.data["id"]
    log = OperationLog.objects.filter(
        action=ACTION_RECOMMENDATION_CREATED, target_type="recommendation_batch", target_id=batch_id
    ).first()
    assert log is not None


def test_select_candidate_action_name(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """选中候选人日志 action 应为 candidate_selected（非旧 select_recommendation_candidate）。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT,
    )
    candidate_staff = create_staff(name="候选人红娘sel")
    candidate_user = create_customer_profile(owner=candidate_staff, gender=CustomerProfile.GENDER_FEMALE)
    batch = RecommendationBatch.objects.create(
        user=user, staff=matchmaker_staff,
        batch_no="REC-OPLOG-SEL-001", candidate_count=1,
        status=RecommendationBatch.STATUS_OPEN,
    )
    candidate = RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)

    resp = auth_client(matchmaker_staff).post(
        f"/api/v1/recommendations/candidates/{candidate.id}/select/"
    )
    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        action=ACTION_CANDIDATE_SELECTED,
        target_type="recommendation_candidate",
        target_id=candidate.id,
    ).first()
    assert log is not None


# ---------------------------------------------------------------------------
# 转移申请
# ---------------------------------------------------------------------------

def test_create_transfer_request_action_name(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """发起转移申请日志 action 应为 transfer_applied（非旧 create_transfer_request）。"""
    user = create_customer_profile(owner=matchmaker_staff)
    to_staff = create_staff(name="目标红娘transfer")
    resp = auth_client(matchmaker_staff).post(
        "/api/v1/transfer-requests/",
        {"user_id": user.id, "to_staff_id": to_staff.id, "reason": "测试转移"},
        format="json",
    )
    assert resp.status_code == 201
    req_id = resp.data["id"]
    log = OperationLog.objects.filter(
        action=ACTION_TRANSFER_APPLIED, target_type="user_transfer_request", target_id=req_id
    ).first()
    assert log is not None


def test_approve_transfer_request_writes_two_logs(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    """审批通过转移后应落两条日志：transfer_approved（申请对象）+ user_owner_changed（用户对象）。"""
    user = create_customer_profile(owner=matchmaker_staff)
    to_staff = create_staff(name="审批目标红娘")
    from apps.transfer.models import UserTransferRequest
    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=matchmaker_staff,
        to_staff=to_staff,
        reason="审批测试",
    )
    resp = auth_client(admin_staff).post(
        f"/api/v1/transfer-requests/{req.id}/approve/",
        {},
        format="json",
    )
    assert resp.status_code == 200

    transfer_log = OperationLog.objects.filter(
        action=ACTION_TRANSFER_APPROVED,
        target_type="user_transfer_request",
        target_id=req.id,
    ).first()
    assert transfer_log is not None

    user_log = OperationLog.objects.filter(
        action=ACTION_USER_OWNER_CHANGED,
        target_type="user",
        target_id=user.id,
    ).first()
    assert user_log is not None
    assert user_log.before_json["owner_id"] == matchmaker_staff.id
    assert user_log.after_json["owner_id"] == to_staff.id


def test_reject_transfer_request_action_name(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    """驳回转移申请日志 action 应为 transfer_rejected（非旧 reject_transfer_request）。"""
    user = create_customer_profile(owner=matchmaker_staff)
    to_staff = create_staff(name="被驳回目标红娘")
    from apps.transfer.models import UserTransferRequest
    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=matchmaker_staff,
        to_staff=to_staff,
        reason="驳回测试",
    )
    resp = auth_client(admin_staff).post(
        f"/api/v1/transfer-requests/{req.id}/reject/",
        {"review_note": "不批"},
        format="json",
    )
    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        action=ACTION_TRANSFER_REJECTED,
        target_type="user_transfer_request",
        target_id=req.id,
    ).first()
    assert log is not None


# ---------------------------------------------------------------------------
# ACTION_DISPLAY_MAP 覆盖验证
# ---------------------------------------------------------------------------

def test_action_display_map_covers_all_canonical_actions(auth_client, admin_staff, matchmaker_staff):
    """ACTION_DISPLAY_MAP 中所有 canonical action 均应有中文展示名，且不回落到 action 原值。"""
    from apps.oplog.serializers import ACTION_DISPLAY_MAP
    from apps.oplog.services import create_operation_log

    canonical_actions = [
        ACTION_USER_CREATED, "user_status_changed", ACTION_USER_PROFILE_UPDATED,
        ACTION_USER_PAUSED, ACTION_USER_RESUMED, ACTION_USER_OWNER_CHANGED,
        ACTION_RECOMMENDATION_CREATED, ACTION_CANDIDATE_SELECTED,
        ACTION_RECOMMENDATION_BATCH_CLOSED,
        "match_card_created", "match_card_stage_changed", "match_card_risk_changed", "match_card_ended",
        ACTION_FOLLOW_UP_CREATED, ACTION_FOLLOW_UP_UPDATED,
        "success_applied", "success_approved", "success_rejected", "success_invalidated",
        ACTION_TRANSFER_APPLIED, ACTION_TRANSFER_APPROVED, ACTION_TRANSFER_REJECTED,
        ACTION_REMINDER_SET, "admin_force_change",
    ]

    for action in canonical_actions:
        assert action in ACTION_DISPLAY_MAP, f"ACTION_DISPLAY_MAP 缺少 action: {action}"
        assert ACTION_DISPLAY_MAP[action] != action, f"action {action} 的展示名不应与 action 值相同"
