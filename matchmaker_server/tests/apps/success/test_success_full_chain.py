"""success 模块全链路专项测试

覆盖目标：
1. approve → SuccessCase 创建 + matched_revisit 过期 + success_revisit 创建 + oplog
2. reject → 阶段回退 + oplog
3. invalidate → 失效联动 + 防重复
4. 重复审批防护（已审批的申请再 approve/reject）
5. invalidate 阶段守卫（stage != success）
6. 端到端全链路：apply → approve → invalidate
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.oplog.models import OperationLog
from apps.reminder.models import Reminder
from apps.reminder.services import create_reminder
from apps.success.models import SuccessApplication, SuccessCase
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------

def _seed_prerequisites(match_card, *, male_count=2, female_count=2):
    """创建满足成功申请前置条件的回访记录 + staff_judgment。"""
    for i in range(male_count):
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_MATCHED,
            match_card=match_card,
            user=match_card.male_user,
            staff=match_card.male_staff,
            content=f"男方回访{i + 1}",
            is_still_contact=FollowUpRecord.CONTACT_YES,
            risk_status=FollowUpRecord.RISK_NONE,
            next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
        )
    for i in range(female_count):
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_MATCHED,
            match_card=match_card,
            user=match_card.female_user,
            staff=match_card.female_staff,
            content=f"女方回访{i + 1}",
            is_still_contact=FollowUpRecord.CONTACT_YES,
            risk_status=FollowUpRecord.RISK_NONE,
            next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
        )
    match_card.staff_judgment = "红娘确认双方已建立恋爱关系"
    match_card.save(update_fields=["staff_judgment", "updated_at"])


@pytest.fixture
def _make_card(create_customer_profile, create_staff):
    """快速创建一张处于 stable_contact、created_at 满30天的配对卡。"""
    def factory(*, primary_staff=None):
        ps = primary_staff or create_staff(name="主操作红娘")
        suffix = f"{uuid4().int % 10**8:08d}"
        male = create_customer_profile(
            owner=ps, name="男方", gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}", wechat=f"m_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female = create_customer_profile(
            owner=ps, name="女方", gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}", wechat=f"f_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        card = MatchCard.objects.create(
            male_user=male, female_user=female,
            male_staff=ps, female_staff=ps, primary_staff=ps,
            stage=MatchCard.STAGE_STABLE_CONTACT,
            risk_level=MatchCard.RISK_NONE,
        )
        # 确保 created_at >= 31 天
        MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
        card.refresh_from_db()
        _seed_prerequisites(card)
        return card, ps
    return factory


# ---------------------------------------------------------------------------
# 1. approve 全链路验证（含 oplog）
# ---------------------------------------------------------------------------

class TestApproveFullChain:

    def test_approve_creates_success_case_and_oplog(self, auth_client, admin_staff, _make_card):
        """approve → SuccessCase 创建 + oplog 写入验证。"""
        card, ps = _make_card()

        # 发起申请
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id, "apply_note": "关系稳定"},
            format="json",
        )
        assert resp.status_code == 201
        app_id = resp.data["id"]

        # admin 审核通过
        resp = auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )
        assert resp.status_code == 200
        assert resp.data["status"] == SuccessApplication.STATUS_APPROVED
        sc_id = resp.data["success_case_id"]

        # 验证 SuccessCase
        sc = SuccessCase.objects.get(pk=sc_id)
        assert sc.status == SuccessCase.STATUS_ACTIVE
        assert sc.match_card_id == card.id
        assert sc.approved_at is not None

        # 验证 oplog
        oplog = OperationLog.objects.get(
            action="success_approved",
            target_type="success_case",
            target_id=sc.id,
        )
        assert oplog.operator_id == admin_staff.id
        assert oplog.after_json["match_card_stage"] == MatchCard.STAGE_SUCCESS
        assert oplog.after_json["success_case_status"] == SuccessCase.STATUS_ACTIVE

    def test_approve_creates_three_success_revisit_reminders(self, auth_client, admin_staff, _make_card):
        """approve → 生成 3 条 success_revisit 提醒（30/90/180天）。"""
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        app_id = resp.data["id"]
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )

        sc = SuccessCase.objects.get(application_id=app_id)
        reminders = list(
            Reminder.objects.filter(
                target_type=Reminder.TARGET_MATCH_CARD,
                target_id=card.id,
                remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            ).order_by("remind_at")
        )
        assert len(reminders) == 3
        for r in reminders:
            assert r.staff_id == ps.id
            assert r.status == Reminder.STATUS_PENDING
        expected_offsets = [30, 90, 180]
        for r, days in zip(reminders, expected_offsets):
            diff = (r.remind_at - sc.approved_at).total_seconds()
            assert abs(diff - days * 86400) < 2  # 允许 2 秒误差

    def test_approve_expires_matched_revisit_and_sets_next_remind_at(
        self, auth_client, admin_staff, _make_card
    ):
        """approve → matched_revisit 过期 + next_remind_at 指向第一条 success_revisit。"""
        card, ps = _make_card()
        # 模拟已有 matched_revisit
        mr = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=5),
        )

        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{resp.data['id']}/approve/",
            {}, format="json",
        )

        mr.refresh_from_db()
        assert mr.status == Reminder.STATUS_EXPIRED

        card.refresh_from_db()
        first_sr = (
            Reminder.objects.filter(
                target_type=Reminder.TARGET_MATCH_CARD,
                target_id=card.id,
                remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            ).order_by("remind_at").first()
        )
        assert first_sr is not None
        assert card.next_remind_at == first_sr.remind_at

    def test_approve_releases_both_users_from_match(self, auth_client, admin_staff, _make_card):
        """approve → 男女双方 is_in_match 置为 False。"""
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{resp.data['id']}/approve/",
            {}, format="json",
        )

        card.male_user.refresh_from_db()
        card.female_user.refresh_from_db()
        assert card.male_user.is_in_match is False
        assert card.female_user.is_in_match is False


# ---------------------------------------------------------------------------
# 2. reject 全链路验证（含 oplog）
# ---------------------------------------------------------------------------

class TestRejectFullChain:

    def test_reject_rolls_back_stage_and_writes_oplog(self, auth_client, admin_staff, _make_card):
        """reject → 阶段回退到 stable_contact + oplog 写入。"""
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        app_id = resp.data["id"]

        card.refresh_from_db()
        assert card.stage == MatchCard.STAGE_SUCCESS_PENDING_REVIEW

        resp = auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/reject/",
            {"review_note": "观察期不够"},
            format="json",
        )
        assert resp.status_code == 200

        card.refresh_from_db()
        assert card.stage == MatchCard.STAGE_STABLE_CONTACT

        oplog = OperationLog.objects.get(
            action="success_rejected",
            target_type="match_card",
            target_id=card.id,
        )
        assert oplog.operator_id == admin_staff.id
        assert oplog.before_json["application_status"] == SuccessApplication.STATUS_PENDING
        assert oplog.after_json["application_status"] == SuccessApplication.STATUS_REJECTED
        assert oplog.after_json["match_card_stage"] == MatchCard.STAGE_STABLE_CONTACT
        assert oplog.reason == "观察期不够"


# ---------------------------------------------------------------------------
# 3. 重复审批防护
# ---------------------------------------------------------------------------

class TestDuplicateReviewGuard:

    def test_cannot_approve_already_approved_application(self, auth_client, admin_staff, _make_card):
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        app_id = resp.data["id"]
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )

        # 再次 approve
        resp2 = auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )
        assert resp2.status_code == 400
        assert resp2.data["code"] == "SUCCESS_APPLICATION_ALREADY_REVIEWED"

    def test_cannot_reject_already_approved_application(self, auth_client, admin_staff, _make_card):
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        app_id = resp.data["id"]
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )

        resp2 = auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/reject/",
            {"review_note": "后悔了"},
            format="json",
        )
        assert resp2.status_code == 400
        assert resp2.data["code"] == "SUCCESS_APPLICATION_ALREADY_REVIEWED"

    def test_cannot_approve_already_rejected_application(self, auth_client, admin_staff, _make_card):
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        app_id = resp.data["id"]
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/reject/",
            {"review_note": "先退回"},
            format="json",
        )

        resp2 = auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )
        assert resp2.status_code == 400
        assert resp2.data["code"] == "SUCCESS_APPLICATION_ALREADY_REVIEWED"


# ---------------------------------------------------------------------------
# 4. invalidate 防护
# ---------------------------------------------------------------------------

class TestInvalidateGuard:

    def _make_active_case(self, _make_card, auth_client, admin_staff):
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{resp.data['id']}/approve/",
            {}, format="json",
        )
        sc = SuccessCase.objects.get(application_id=resp.data["id"])
        return card, ps, sc

    def test_cannot_invalidate_already_invalidated_case(
        self, auth_client, admin_staff, _make_card, create_reason_enum
    ):
        card, ps, sc = self._make_active_case(_make_card, auth_client, admin_staff)
        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
            label="双方分手",
        )

        # 第一次失效
        resp = auth_client(ps).post(
            f"/api/v1/success-cases/{sc.id}/invalidate/",
            {"reason_id": reason.id},
            format="json",
        )
        assert resp.status_code == 200

        # 第二次失效
        resp2 = auth_client(ps).post(
            f"/api/v1/success-cases/{sc.id}/invalidate/",
            {"reason_id": reason.id},
            format="json",
        )
        assert resp2.status_code == 400
        assert resp2.data["code"] == "SUCCESS_CASE_ALREADY_INVALIDATED"

    def test_cannot_invalidate_when_stage_is_not_success(
        self, auth_client, admin_staff, _make_card, create_reason_enum
    ):
        """手动把 stage 改掉后再 invalidate 应报错。"""
        card, ps, sc = self._make_active_case(_make_card, auth_client, admin_staff)
        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
            label="双方分手2",
        )

        # 强制修改 stage
        card.stage = MatchCard.STAGE_ENDED
        card.save(update_fields=["stage", "updated_at"])

        resp = auth_client(ps).post(
            f"/api/v1/success-cases/{sc.id}/invalidate/",
            {"reason_id": reason.id},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "MATCH_STAGE_TRANSITION_INVALID"


# ---------------------------------------------------------------------------
# 5. invalidate 联动验证
# ---------------------------------------------------------------------------

class TestInvalidateChain:

    def test_invalidate_expires_success_revisit_and_clears_next_remind(
        self, auth_client, admin_staff, _make_card, create_reason_enum
    ):
        """invalidate → success_revisit 过期 + next_remind_at = None + ended_at 设定。"""
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{resp.data['id']}/approve/",
            {}, format="json",
        )
        sc = SuccessCase.objects.get(application_id=resp.data["id"])

        # 确认 success_revisit 存在
        sr_count = Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            status=Reminder.STATUS_PENDING,
        ).count()
        assert sr_count == 3

        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
            label="关系破裂",
        )
        resp = auth_client(ps).post(
            f"/api/v1/success-cases/{sc.id}/invalidate/",
            {"reason_id": reason.id, "reason_note": "不联系了"},
            format="json",
        )
        assert resp.status_code == 200

        # success_revisit 全部过期
        active_sr = Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            status__in=[Reminder.STATUS_PENDING, Reminder.STATUS_SENT],
        ).count()
        assert active_sr == 0

        card.refresh_from_db()
        assert card.stage == MatchCard.STAGE_ENDED
        assert card.ended_at is not None
        assert card.next_remind_at is None

    def test_invalidate_writes_oplog(
        self, auth_client, admin_staff, _make_card, create_reason_enum
    ):
        card, ps = _make_card()
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id}, format="json",
        )
        auth_client(admin_staff).post(
            f"/api/v1/success-applications/{resp.data['id']}/approve/",
            {}, format="json",
        )
        sc = SuccessCase.objects.get(application_id=resp.data["id"])

        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
            label="感情不合",
        )
        auth_client(ps).post(
            f"/api/v1/success-cases/{sc.id}/invalidate/",
            {"reason_id": reason.id, "reason_note": "双方已分手"},
            format="json",
        )

        oplog = OperationLog.objects.get(
            action="success_invalidated",
            target_type="success_case",
            target_id=sc.id,
        )
        assert oplog.operator_id == ps.id
        assert oplog.before_json["success_case_status"] == SuccessCase.STATUS_ACTIVE
        assert oplog.after_json["success_case_status"] == SuccessCase.STATUS_INVALIDATED
        assert oplog.after_json["match_card_stage"] == MatchCard.STAGE_ENDED
        assert oplog.reason == "双方已分手"


# ---------------------------------------------------------------------------
# 6. 端到端全链路：apply → approve → invalidate
# ---------------------------------------------------------------------------

class TestEndToEndChain:

    def test_full_lifecycle_apply_approve_invalidate(
        self, auth_client, admin_staff, _make_card, create_reason_enum
    ):
        """单测试贯穿 apply → approve → invalidate 全链路，验证每步关键状态。"""
        card, ps = _make_card()

        # --- 步骤1：发起申请 ---
        resp = auth_client(ps).post(
            "/api/v1/success-applications/",
            {"match_card_id": card.id, "apply_note": "双方已确认恋爱关系"},
            format="json",
        )
        assert resp.status_code == 201
        app_id = resp.data["id"]

        card.refresh_from_db()
        assert card.stage == MatchCard.STAGE_SUCCESS_PENDING_REVIEW
        assert card.male_user.is_in_match is True  # 申请期间仍在配对中

        # --- 步骤2：管理员审核通过 ---
        resp = auth_client(admin_staff).post(
            f"/api/v1/success-applications/{app_id}/approve/",
            {}, format="json",
        )
        assert resp.status_code == 200
        sc_id = resp.data["success_case_id"]

        card.refresh_from_db()
        card.male_user.refresh_from_db()
        card.female_user.refresh_from_db()
        assert card.stage == MatchCard.STAGE_SUCCESS
        assert card.male_user.is_in_match is False
        assert card.female_user.is_in_match is False

        # success_revisit 已创建
        sr_count = Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            status=Reminder.STATUS_PENDING,
        ).count()
        assert sr_count == 3

        # next_remind_at 指向第一条 success_revisit
        first_sr = (
            Reminder.objects.filter(
                target_type=Reminder.TARGET_MATCH_CARD,
                target_id=card.id,
                remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            ).order_by("remind_at").first()
        )
        assert card.next_remind_at == first_sr.remind_at

        # --- 步骤3：标记失效 ---
        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
            label="双方分手-全链路",
        )
        resp = auth_client(ps).post(
            f"/api/v1/success-cases/{sc_id}/invalidate/",
            {"reason_id": reason.id, "reason_note": "确认分手"},
            format="json",
        )
        assert resp.status_code == 200

        sc = SuccessCase.objects.get(pk=sc_id)
        card.refresh_from_db()
        assert sc.status == SuccessCase.STATUS_INVALIDATED
        assert sc.invalidated_at is not None
        assert card.stage == MatchCard.STAGE_ENDED
        assert card.ended_at is not None
        assert card.next_remind_at is None

        # success_revisit 全部过期
        active_sr = Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            status__in=[Reminder.STATUS_PENDING, Reminder.STATUS_SENT],
        ).count()
        assert active_sr == 0

        # 操作日志链完整
        assert OperationLog.objects.filter(action="success_applied", target_id=card.id).exists()
        assert OperationLog.objects.filter(action="success_approved", target_id=sc_id).exists()
        assert OperationLog.objects.filter(action="success_invalidated", target_id=sc_id).exists()
