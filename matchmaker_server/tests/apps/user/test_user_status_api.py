import pytest
from rest_framework import status

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.oplog.models import OperationLog
from apps.user.models import CustomerProfile, UserStatusHistory


pytestmark = pytest.mark.django_db


def test_change_status_allows_valid_owner_transition(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {
            "to_status": CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            "reason": "首次沟通完成",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["pool_status"] == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert response.data["force_applied"] is False

    user.refresh_from_db()
    assert user.last_action_at is not None
    history = UserStatusHistory.objects.filter(user=user).latest("id")
    assert history.from_status == CustomerProfile.STATUS_NEW_PENDING
    assert history.to_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert history.reason == "首次沟通完成"

    oplog = OperationLog.objects.filter(target_type="user", target_id=user.id).latest("id")
    assert oplog.action == "user_status_changed"
    assert oplog.reason == "首次沟通完成"
    assert oplog.before_json["pool_status"] == CustomerProfile.STATUS_NEW_PENDING
    assert oplog.after_json["pool_status"] == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND


def test_change_status_blocks_invalid_transition(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {"to_status": CustomerProfile.STATUS_SELECTED_PENDING_MEET},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "USER_STATUS_TRANSITION_INVALID"


def test_change_status_allows_selected_pending_meet_to_met_not_continue(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {"to_status": CustomerProfile.STATUS_MET_NOT_CONTINUE},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["pool_status"] == CustomerProfile.STATUS_MET_NOT_CONTINUE

    user.refresh_from_db()
    assert user.pool_status == CustomerProfile.STATUS_MET_NOT_CONTINUE
    history = UserStatusHistory.objects.filter(user=user).latest("id")
    assert history.from_status == CustomerProfile.STATUS_SELECTED_PENDING_MEET
    assert history.to_status == CustomerProfile.STATUS_MET_NOT_CONTINUE


def test_change_status_blocks_met_not_continue_exit_without_followup(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_MET_NOT_CONTINUE)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {"to_status": CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "FAILURE_REASON_REQUIRED"

    user.refresh_from_db()
    assert user.pool_status == CustomerProfile.STATUS_MET_NOT_CONTINUE


def test_change_status_allows_met_not_continue_exit_with_failure_followup(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
    create_reason_enum,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_MET_NOT_CONTINUE)
    # 创建进入 met_not_continue 的状态历史记录
    UserStatusHistory.objects.create(
        user=user,
        from_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        to_status=CustomerProfile.STATUS_MET_NOT_CONTINUE,
        changed_by=matchmaker_staff,
    )
    failure_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_MEET_FAILURE,
        label="节奏不合适",
        sort_order=1,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user,
        staff=matchmaker_staff,
        content="见面后双方节奏不一致",
        failure_reason=failure_reason,
    )

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {"to_status": CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["pool_status"] == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND

    user.refresh_from_db()
    assert user.pool_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert "待重新推荐" in user.tags


def test_change_status_blocks_met_not_continue_exit_with_stale_failure_record(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
    create_reason_enum,
):
    """上一轮 met_not_continue 的失败记录不应计入本轮。"""
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET)
    failure_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_MEET_FAILURE,
        label="性格不合",
        sort_order=2,
    )
    # 旧的失败跟进记录（本轮进入 met_not_continue 之前创建）
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user,
        staff=matchmaker_staff,
        content="上一轮的失败原因",
        failure_reason=failure_reason,
    )
    # 模拟本轮进入 met_not_continue
    user.pool_status = CustomerProfile.STATUS_MET_NOT_CONTINUE
    user.save(update_fields=["pool_status"])
    UserStatusHistory.objects.create(
        user=user,
        from_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        to_status=CustomerProfile.STATUS_MET_NOT_CONTINUE,
        changed_by=matchmaker_staff,
    )

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {"to_status": CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "FAILURE_REASON_REQUIRED"


def test_matchmaker_cannot_force_change_status(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {
            "to_status": CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            "force": True,
            "force_reason": "测试强制跳转",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_admin_force_change_requires_reason(auth_client, admin_staff, create_customer_profile):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)

    response = auth_client(admin_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {
            "to_status": CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            "force": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "FORCE_REASON_REQUIRED"


def test_admin_force_change_can_skip_whitelist_and_write_history_and_log(
    auth_client,
    admin_staff,
    create_customer_profile,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)

    response = auth_client(admin_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {
            "to_status": CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            "force": True,
            "force_reason": "管理员手动调整",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["force_applied"] is True
    user.refresh_from_db()
    assert user.pool_status == CustomerProfile.STATUS_SELECTED_PENDING_MEET

    history = UserStatusHistory.objects.filter(user=user).latest("id")
    assert history.reason_id is None
    assert history.reason_note == "管理员手动调整"

    oplog = OperationLog.objects.filter(target_type="user", target_id=user.id).latest("id")
    assert oplog.action == "admin_force_change"
    assert oplog.reason == "管理员手动调整"


def test_pause_requires_pause_reason(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/pause/",
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "PAUSE_REASON_REQUIRED"


def test_pause_writes_pre_pause_status_and_history(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
    create_reason_enum,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT)
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="暂停测试原因", sort_order=99)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/pause/",
        {
            "reason_id": reason.id,
            "reason_note": "用户最近太忙",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["pool_status"] == CustomerProfile.STATUS_PAUSED
    assert response.data["pre_pause_status"] == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT

    user.refresh_from_db()
    assert user.pre_pause_status == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    history = UserStatusHistory.objects.filter(user=user).latest("id")
    assert history.reason_id_id == reason.id
    assert history.reason_note == "用户最近太忙"

    oplog = OperationLog.objects.filter(target_type="user", target_id=user.id).latest("id")
    assert oplog.action == "user_status_changed"
    assert oplog.reason == "用户最近太忙"
    assert oplog.before_json["pool_status"] == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    assert oplog.after_json["pool_status"] == CustomerProfile.STATUS_PAUSED
    assert oplog.after_json["pre_pause_status"] == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT


def test_pause_rejects_met_not_continue(auth_client, matchmaker_staff, create_customer_profile, create_reason_enum):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_MET_NOT_CONTINUE)
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="暂停测试原因2", sort_order=100)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/pause/",
        {"reason_id": reason.id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "USER_STATUS_TRANSITION_INVALID"


def test_non_owner_matchmaker_cannot_pause(auth_client, create_staff, create_customer_profile, create_reason_enum):
    owner = create_staff(phone="13800138121", name="红娘A")
    outsider = create_staff(phone="13800138122", name="红娘B")
    user = create_customer_profile(owner=owner, pool_status=CustomerProfile.STATUS_NEW_PENDING)
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="暂停测试原因3", sort_order=101)

    response = auth_client(outsider).post(
        f"/api/v1/users/{user.id}/pause/",
        {"reason_id": reason.id},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_resume_restores_pre_pause_status_and_writes_history(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
):
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_PAUSED,
        pre_pause_status=CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT,
    )

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/resume/",
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["pool_status"] == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT

    user.refresh_from_db()
    assert user.pre_pause_status is None
    history = UserStatusHistory.objects.filter(user=user).latest("id")
    assert history.from_status == CustomerProfile.STATUS_PAUSED
    assert history.to_status == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    assert history.reason_note == "恢复服务"

    oplog = OperationLog.objects.filter(target_type="user", target_id=user.id).latest("id")
    assert oplog.action == "user_status_changed"
    assert oplog.reason == "恢复服务"
    assert oplog.before_json["pool_status"] == CustomerProfile.STATUS_PAUSED
    assert oplog.after_json["pool_status"] == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    assert oplog.after_json["pre_pause_status"] is None


def test_resume_rejects_non_paused_user(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/resume/",
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "USER_STATUS_TRANSITION_INVALID"


# ── A2: last_unmatched_active_at tests ──────────────────────────────────


def test_change_status_updates_last_unmatched_active_at(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)
    assert user.last_unmatched_active_at is None

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {"to_status": CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.last_unmatched_active_at is not None


def test_pause_does_not_update_last_unmatched_active_at(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
    create_reason_enum,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)
    assert user.last_unmatched_active_at is None
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="暂停A2测试", sort_order=200)

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/pause/",
        {"reason_id": reason.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.last_unmatched_active_at is None


def test_resume_updates_last_unmatched_active_at(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
):
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_PAUSED,
        pre_pause_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )
    assert user.last_unmatched_active_at is None

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/users/{user.id}/resume/",
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.last_unmatched_active_at is not None


def test_admin_force_to_paused_does_not_update_last_unmatched_active_at(
    auth_client,
    admin_staff,
    create_customer_profile,
):
    user = create_customer_profile(pool_status=CustomerProfile.STATUS_NEW_PENDING)
    assert user.last_unmatched_active_at is None

    response = auth_client(admin_staff).post(
        f"/api/v1/users/{user.id}/change-status/",
        {
            "to_status": CustomerProfile.STATUS_PAUSED,
            "force": True,
            "force_reason": "管理员强制暂停",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.last_unmatched_active_at is None
