"""转移申请 approve / reject 全链路专项测试

覆盖目标：
1. approve → oplog 正确写入（transfer_approved + user_owner_changed 两条）
2. approve → 相关 reminder staff 同步（user 级 + match_card 级）
3. approve → 女方用户侧 match card female_staff 同步
4. reject → oplog 正确写入（transfer_rejected）
5. reject → review_note 正确记录
6. 交叉防重入：approve 后 reject / reject 后 approve
7. create → oplog 正确写入（transfer_applied）
8. e2e：create → approve 全链路副作用验证
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.matchcard.models import MatchCard
from apps.oplog.models import OperationLog
from apps.reminder.models import Reminder
from apps.reminder.services import create_reminder
from apps.transfer.models import UserTransferRequest
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pending_req(user, from_staff, to_staff, reason="测试原因"):
    return UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason=reason,
        status=UserTransferRequest.STATUS_PENDING,
    )


def _make_user(create_customer_profile, owner, **kwargs):
    suffix = f"{uuid4().int % 10**8:08d}"
    return create_customer_profile(
        owner=owner,
        phone=f"138{suffix}",
        wechat=f"wx_{suffix}",
        **kwargs,
    )


def _make_match_card(male_user, female_user, male_staff, female_staff, **kwargs):
    defaults = dict(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_staff,
        female_staff=female_staff,
        primary_staff=male_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
        risk_level=MatchCard.RISK_NONE,
    )
    defaults.update(kwargs)
    return MatchCard.objects.create(**defaults)


# ===========================================================================
# approve → oplog
# ===========================================================================

class TestApproveOplog:

    def test_approve_creates_two_oplogs(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """approve 写入 transfer_approved 和 user_owner_changed 两条 oplog。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        before_count = OperationLog.objects.count()
        auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")

        new_logs = OperationLog.objects.filter(id__gt=0).order_by("id")[before_count:]
        actions = [log.action for log in new_logs]
        assert "transfer_approved" in actions
        assert "user_owner_changed" in actions

    def test_approve_oplog_transfer_approved_content(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """transfer_approved oplog 包含正确的 before/after json。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")

        log = OperationLog.objects.filter(
            action="transfer_approved",
            target_type="user_transfer_request",
            target_id=req.id,
        ).first()
        assert log is not None
        assert log.operator_id == admin_staff.id
        assert log.before_json["owner_id"] == matchmaker_staff.id
        assert log.after_json["owner_id"] == to_staff.id
        assert log.after_json["status"] == "approved"

    def test_approve_oplog_user_owner_changed_content(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """user_owner_changed oplog target_type=user, target_id=user.id。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")

        log = OperationLog.objects.filter(
            action="user_owner_changed",
            target_type="user",
            target_id=user.id,
        ).first()
        assert log is not None
        assert log.before_json["owner_id"] == matchmaker_staff.id
        assert log.after_json["owner_id"] == to_staff.id


# ===========================================================================
# approve → reminder staff 同步
# ===========================================================================

class TestApproveReminderSync:

    def test_approve_syncs_user_level_pending_reminders(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """approve 后，用户级 pending reminder 的 staff 同步为 to_staff。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)

        # 创建用户级 pending reminder
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=matchmaker_staff,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() + timedelta(days=3),
        )

        req = _pending_req(user, matchmaker_staff, to_staff)
        auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")

        reminder.refresh_from_db()
        assert reminder.staff_id == to_staff.id

    def test_approve_syncs_match_card_level_pending_reminders(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """approve 后，配对卡级 pending reminder (matched_revisit/manual) 的 staff 同步。"""
        to_staff = create_staff(name="接收红娘")
        female_staff = create_staff(name="女方红娘")

        male = _make_user(
            create_customer_profile, matchmaker_staff,
            gender=CustomerProfile.GENDER_MALE,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female = _make_user(
            create_customer_profile, female_staff,
            gender=CustomerProfile.GENDER_FEMALE,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        mc = _make_match_card(male, female, matchmaker_staff, female_staff)

        # 配对卡级 reminder，staff 指向 matchmaker_staff
        reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=mc.id,
            staff=matchmaker_staff,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=7),
        )

        req = _pending_req(male, matchmaker_staff, to_staff)
        auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")

        reminder.refresh_from_db()
        assert reminder.staff_id == to_staff.id

    def test_approve_does_not_sync_sent_reminders(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """approve 只同步 pending reminders，sent 状态的不动。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)

        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=matchmaker_staff,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() + timedelta(days=3),
            status_value=Reminder.STATUS_SENT,
        )

        req = _pending_req(user, matchmaker_staff, to_staff)
        auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")

        reminder.refresh_from_db()
        assert reminder.staff_id == matchmaker_staff.id  # 不变


# ===========================================================================
# approve → 女方侧 match card staff 同步
# ===========================================================================

class TestApproveFemaleStaffSync:

    def test_approve_syncs_female_staff_when_transferring_female_user(
        self, auth_client, admin_staff, create_customer_profile, create_staff,
    ):
        """转移女方用户时，配对卡 female_staff 同步为 to_staff。"""
        female_owner = create_staff(name="女方原红娘")
        male_owner = create_staff(name="男方红娘")
        to_staff = create_staff(name="女方新红娘")

        male = _make_user(
            create_customer_profile, male_owner,
            gender=CustomerProfile.GENDER_MALE,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female = _make_user(
            create_customer_profile, female_owner,
            gender=CustomerProfile.GENDER_FEMALE,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        mc = _make_match_card(male, female, male_owner, female_owner)

        req = _pending_req(female, female_owner, to_staff)
        resp = auth_client(admin_staff).post(f"/api/v1/transfer-requests/{req.id}/approve/")
        assert resp.status_code == 200

        mc.refresh_from_db()
        assert mc.female_staff_id == to_staff.id
        assert mc.male_staff_id == male_owner.id  # 男方侧不变

        affected = resp.json()["affected_match_cards"]
        assert any(a["id"] == mc.id and a["updated_field"] == "female_staff_id" for a in affected)


# ===========================================================================
# reject → oplog + review_note
# ===========================================================================

class TestRejectOplog:

    def test_reject_creates_oplog(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """reject 写入 transfer_rejected oplog。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        auth_client(admin_staff).post(
            f"/api/v1/transfer-requests/{req.id}/reject/",
            data={"review_note": "暂不批准"},
            format="json",
        )

        log = OperationLog.objects.filter(
            action="transfer_rejected",
            target_type="user_transfer_request",
            target_id=req.id,
        ).first()
        assert log is not None
        assert log.operator_id == admin_staff.id
        assert log.after_json["status"] == "rejected"
        assert log.after_json["review_note"] == "暂不批准"

    def test_reject_does_not_create_user_owner_changed_oplog(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """reject 不应写入 user_owner_changed oplog。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        before_count = OperationLog.objects.filter(action="user_owner_changed").count()

        auth_client(admin_staff).post(
            f"/api/v1/transfer-requests/{req.id}/reject/",
            data={},
            format="json",
        )

        after_count = OperationLog.objects.filter(action="user_owner_changed").count()
        assert after_count == before_count

    def test_reject_review_note_persisted(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """reject 后 review_note 在模型中正确持久化。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        auth_client(admin_staff).post(
            f"/api/v1/transfer-requests/{req.id}/reject/",
            data={"review_note": "资源不足，暂不转移"},
            format="json",
        )

        req.refresh_from_db()
        assert req.review_note == "资源不足，暂不转移"
        assert req.reviewed_at is not None


# ===========================================================================
# 交叉防重入
# ===========================================================================

class TestCrossGuard:

    def test_approve_then_reject_blocked(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """已 approve 的申请再 reject 应返回 TRANSFER_NOT_PENDING。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        client = auth_client(admin_staff)
        resp1 = client.post(f"/api/v1/transfer-requests/{req.id}/approve/")
        assert resp1.status_code == 200

        resp2 = client.post(
            f"/api/v1/transfer-requests/{req.id}/reject/",
            data={"review_note": "想反悔"},
            format="json",
        )
        assert resp2.status_code == 400
        assert resp2.json()["code"] == "TRANSFER_NOT_PENDING"

    def test_reject_then_approve_blocked(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """已 reject 的申请再 approve 应返回 TRANSFER_NOT_PENDING。"""
        to_staff = create_staff(name="接收红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)
        req = _pending_req(user, matchmaker_staff, to_staff)

        client = auth_client(admin_staff)
        resp1 = client.post(
            f"/api/v1/transfer-requests/{req.id}/reject/",
            data={},
            format="json",
        )
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/v1/transfer-requests/{req.id}/approve/")
        assert resp2.status_code == 400
        assert resp2.json()["code"] == "TRANSFER_NOT_PENDING"


# ===========================================================================
# create → oplog
# ===========================================================================

class TestCreateOplog:

    def test_create_writes_transfer_applied_oplog(
        self, auth_client, matchmaker_staff, create_customer_profile, create_staff,
    ):
        """发起转移写入 transfer_applied oplog。"""
        to_staff = create_staff(name="目标红娘")
        user = _make_user(create_customer_profile, matchmaker_staff)

        resp = auth_client(matchmaker_staff).post(
            "/api/v1/transfer-requests/",
            data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "休假转移"},
            format="json",
        )
        assert resp.status_code == 201
        req_id = resp.json()["id"]

        log = OperationLog.objects.filter(
            action="transfer_applied",
            target_type="user_transfer_request",
            target_id=req_id,
        ).first()
        assert log is not None
        assert log.operator_id == matchmaker_staff.id
        assert log.after_json["from_staff_id"] == matchmaker_staff.id
        assert log.after_json["to_staff_id"] == to_staff.id


# ===========================================================================
# E2E: create → approve 全链路
# ===========================================================================

class TestE2ECreateApprove:

    def test_full_chain_create_then_approve(
        self, auth_client, admin_staff, matchmaker_staff,
        create_customer_profile, create_staff,
    ):
        """完整链路：红娘发起 → admin 审批 → 所有副作用验证。"""
        to_staff = create_staff(name="接收红娘")
        female_staff = create_staff(name="女方红娘")

        male = _make_user(
            create_customer_profile, matchmaker_staff,
            gender=CustomerProfile.GENDER_MALE,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female = _make_user(
            create_customer_profile, female_staff,
            gender=CustomerProfile.GENDER_FEMALE,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        mc = _make_match_card(male, female, matchmaker_staff, female_staff)

        # 创建 pending reminder（用户级 + 配对卡级）
        user_reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=male.id,
            staff=matchmaker_staff,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() + timedelta(days=5),
        )
        card_reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=mc.id,
            staff=matchmaker_staff,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=7),
        )

        # Step 1: 红娘发起
        resp1 = auth_client(matchmaker_staff).post(
            "/api/v1/transfer-requests/",
            data={"user_id": male.id, "to_staff_id": to_staff.id, "reason": "工作调整"},
            format="json",
        )
        assert resp1.status_code == 201
        req_id = resp1.json()["id"]

        # Step 2: admin 审批
        resp2 = auth_client(admin_staff).post(
            f"/api/v1/transfer-requests/{req_id}/approve/",
        )
        assert resp2.status_code == 200

        # 验证 1：user.owner 变更
        male.refresh_from_db()
        assert male.owner_id == to_staff.id
        assert male.last_action_at is not None

        # 验证 2：match card male_staff 同步
        mc.refresh_from_db()
        assert mc.male_staff_id == to_staff.id
        assert mc.female_staff_id == female_staff.id  # 女方不变

        # 验证 3：reminder staff 同步
        user_reminder.refresh_from_db()
        assert user_reminder.staff_id == to_staff.id

        card_reminder.refresh_from_db()
        assert card_reminder.staff_id == to_staff.id

        # 验证 4：oplog 完整
        applied_log = OperationLog.objects.filter(
            action="transfer_applied", target_id=req_id
        ).exists()
        approved_log = OperationLog.objects.filter(
            action="transfer_approved", target_id=req_id
        ).exists()
        owner_changed_log = OperationLog.objects.filter(
            action="user_owner_changed", target_id=male.id
        ).exists()
        assert applied_log
        assert approved_log
        assert owner_changed_log

        # 验证 5：申请记录状态正确
        req = UserTransferRequest.objects.get(id=req_id)
        assert req.status == UserTransferRequest.STATUS_APPROVED
        assert req.reviewer_id == admin_staff.id
        assert req.reviewed_at is not None
