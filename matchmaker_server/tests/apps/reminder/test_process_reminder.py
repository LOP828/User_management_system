"""process_reminder 专项测试

覆盖目标：
1. 各 remind_type 处理后的状态变化
2. match_card target 处理后 touch 双方用户 + refresh next_remind_at
3. user target 处理后 touch last_action_at（不创建 followup）
4. first_meet_overdue 创建 unmatched followup + overdue_reason 写入
5. sent 状态可处理 / expired 状态不可处理
6. 多条提醒场景下处理一条后 next_remind_at 指向剩余最早
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.oplog.models import OperationLog
from apps.oplog.services import ACTION_FOLLOW_UP_CREATED
from apps.reminder.models import Reminder
from apps.reminder.services import create_reminder, process_reminder
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _make_card(create_customer_profile, create_staff):
    """创建一张配对卡。"""
    def factory(*, stage=MatchCard.STAGE_INITIAL_CONTACT, primary_staff=None):
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
            stage=stage, risk_level=MatchCard.RISK_NONE,
        )
        return card, ps
    return factory


# ---------------------------------------------------------------------------
# 1. matched_revisit 处理
# ---------------------------------------------------------------------------

class TestProcessMatchedRevisit:

    def test_process_marks_processed_and_touches_users(self, _make_card):
        card, ps = _make_card()
        reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=7),
        )
        result = process_reminder(reminder, ps)

        assert result["status"] == Reminder.STATUS_PROCESSED
        assert result["processed_at"] is not None
        assert "created_follow_up_id" not in result  # 不创建 followup

        reminder.refresh_from_db()
        card.male_user.refresh_from_db()
        card.female_user.refresh_from_db()
        assert reminder.status == Reminder.STATUS_PROCESSED
        assert card.male_user.last_action_at is not None
        assert card.female_user.last_action_at is not None

    def test_process_refreshes_next_remind_at(self, _make_card):
        """处理一条后 next_remind_at 应指向剩余最早提醒。"""
        card, ps = _make_card()
        earlier = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=3),
        )
        later = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=10),
        )

        process_reminder(earlier, ps)

        card.refresh_from_db()
        assert card.next_remind_at == later.remind_at

    def test_process_last_reminder_sets_next_remind_at_none(self, _make_card):
        """处理完唯一 active persisted reminder 后，无 active 行，next_remind_at = None。

        注意：即使 processed 行仍存在，has_persisted_reminders 仍为 True，
        不会回退到 derived 逻辑，所以 next_remind_at = None 是正确行为。
        """
        card, ps = _make_card()
        only = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=3),
        )

        process_reminder(only, ps)

        card.refresh_from_db()
        assert card.next_remind_at is None


# ---------------------------------------------------------------------------
# 2. success_revisit 处理
# ---------------------------------------------------------------------------

class TestProcessSuccessRevisit:

    def test_process_marks_processed_and_refreshes_next_remind(self, _make_card):
        card, ps = _make_card(stage=MatchCard.STAGE_SUCCESS)
        r30 = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            remind_at=timezone.now() + timedelta(days=30),
        )
        r90 = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            remind_at=timezone.now() + timedelta(days=90),
        )

        result = process_reminder(r30, ps)

        assert result["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" not in result

        card.refresh_from_db()
        assert card.next_remind_at == r90.remind_at


# ---------------------------------------------------------------------------
# 3. manual（match_card target）处理
# ---------------------------------------------------------------------------

class TestProcessManualMatchCard:

    def test_process_marks_processed_and_touches_users(self, _make_card):
        card, ps = _make_card()
        reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MANUAL,
            remind_at=timezone.now() + timedelta(days=2),
            is_manual=True,
        )

        result = process_reminder(reminder, ps)

        assert result["status"] == Reminder.STATUS_PROCESSED
        reminder.refresh_from_db()
        assert reminder.status == Reminder.STATUS_PROCESSED

        card.male_user.refresh_from_db()
        card.female_user.refresh_from_db()
        assert card.male_user.last_action_at is not None
        assert card.female_user.last_action_at is not None


# ---------------------------------------------------------------------------
# 4. followup_timeout 处理（user target，不创建 followup）
# ---------------------------------------------------------------------------

class TestProcessFollowupTimeout:

    def test_process_updates_last_action_without_followup(self, create_customer_profile, create_staff):
        owner = create_staff(name="跟进超时红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100001", wechat="ft_process_1",
        )
        baseline = user.last_unmatched_active_at
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() - timedelta(hours=1),
        )

        result = process_reminder(reminder, owner)

        assert result["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" not in result  # 不创建 followup

        user.refresh_from_db()
        assert user.last_action_at is not None
        # followup_timeout 不更新 last_unmatched_active_at
        assert user.last_unmatched_active_at == baseline

        # 确认没有产生 followup 记录
        assert FollowUpRecord.objects.filter(user=user).count() == 0


# ---------------------------------------------------------------------------
# 5. pause_revisit 处理（user target，不创建 followup）
# ---------------------------------------------------------------------------

class TestProcessPauseRevisit:

    def test_process_updates_last_action_without_followup(self, create_customer_profile, create_staff):
        owner = create_staff(name="暂停回访红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100002", wechat="pr_process_1",
            pool_status=CustomerProfile.STATUS_PAUSED,
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_PAUSE_REVISIT,
            remind_at=timezone.now() - timedelta(hours=1),
        )

        result = process_reminder(reminder, owner)

        assert result["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" not in result

        user.refresh_from_db()
        assert user.last_action_at is not None
        assert FollowUpRecord.objects.filter(user=user).count() == 0


# ---------------------------------------------------------------------------
# 6. first_meet_overdue 全链路
# ---------------------------------------------------------------------------

class TestProcessFirstMeetOverdue:

    def test_creates_unmatched_followup_with_reason(self, create_customer_profile, create_staff, create_reason_enum):
        owner = create_staff(name="首见超时红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100003", wechat="fmo_process_1",
        )
        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_OVERDUE,
            label="沟通未到位",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
            remind_at=timezone.now() - timedelta(days=2),
        )
        baseline = user.last_unmatched_active_at

        result = process_reminder(
            reminder, owner,
            overdue_reason=reason,
            overdue_reason_note="已安排重新推荐",
        )

        assert result["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" in result

        followup = FollowUpRecord.objects.get(id=result["created_follow_up_id"])
        assert followup.scene == FollowUpRecord.SCENE_UNMATCHED
        assert followup.user_id == user.id
        assert followup.staff_id == owner.id
        assert followup.overdue_reason_id == reason.id
        assert followup.overdue_reason_note == "已安排重新推荐"
        assert followup.content == "处理未首见超时提醒"

        log = OperationLog.objects.filter(
            action=ACTION_FOLLOW_UP_CREATED,
            target_type="follow_up",
            target_id=followup.id,
        ).first()
        assert log is not None
        assert log.operator_id == owner.id
        assert log.after_json["scene"] == FollowUpRecord.SCENE_UNMATCHED
        assert log.after_json["user_id"] == user.id
        assert log.after_json["match_card_id"] is None

        user.refresh_from_db()
        assert user.last_action_at is not None
        assert user.last_unmatched_active_at > baseline  # 更新了基线

    def test_non_first_meet_overdue_branch_does_not_write_follow_up_created_log(
        self,
        create_customer_profile,
        create_staff,
    ):
        owner = create_staff(name="普通提醒红娘")
        user = create_customer_profile(
            owner=owner,
            phone="13900100010",
            wechat="no_followup_log",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() - timedelta(hours=1),
        )

        before_count = OperationLog.objects.filter(action=ACTION_FOLLOW_UP_CREATED).count()
        result = process_reminder(reminder, owner)

        assert result["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" not in result
        assert OperationLog.objects.filter(action=ACTION_FOLLOW_UP_CREATED).count() == before_count

    def test_rejects_wrong_category_reason(self, create_customer_profile, create_staff, create_reason_enum):
        owner = create_staff(name="首见错误原因红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100004", wechat="fmo_bad_reason",
        )
        pause_reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_PAUSE,
            label="工作忙",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
            remind_at=timezone.now() - timedelta(days=1),
        )

        with pytest.raises(BusinessRuleError) as exc_info:
            process_reminder(reminder, owner, overdue_reason=pause_reason)

        assert exc_info.value.code == "OVERDUE_REASON_REQUIRED"
        assert OperationLog.objects.filter(action=ACTION_FOLLOW_UP_CREATED).count() == 0

    def test_without_note_still_succeeds(self, create_customer_profile, create_staff, create_reason_enum):
        owner = create_staff(name="首见无备注红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100005", wechat="fmo_no_note",
        )
        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_OVERDUE,
            label="库存不足2",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
            remind_at=timezone.now() - timedelta(days=1),
        )

        result = process_reminder(reminder, owner, overdue_reason=reason)

        assert result["status"] == Reminder.STATUS_PROCESSED
        followup = FollowUpRecord.objects.get(id=result["created_follow_up_id"])
        assert followup.overdue_reason_note is None


# ---------------------------------------------------------------------------
# 7. sent 状态可处理 / expired 不可处理
# ---------------------------------------------------------------------------

class TestStatusGuard:

    def test_sent_reminder_can_be_processed(self, create_customer_profile, create_staff):
        owner = create_staff(name="sent处理红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100006", wechat="sent_process",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_NORMAL,
            remind_at=timezone.now() + timedelta(hours=1),
            status_value=Reminder.STATUS_SENT,
        )

        result = process_reminder(reminder, owner)

        assert result["status"] == Reminder.STATUS_PROCESSED
        reminder.refresh_from_db()
        assert reminder.status == Reminder.STATUS_PROCESSED

    def test_expired_reminder_cannot_be_processed(self, create_customer_profile, create_staff):
        owner = create_staff(name="expired处理红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100007", wechat="expired_process",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_NORMAL,
            remind_at=timezone.now() + timedelta(hours=1),
            status_value=Reminder.STATUS_EXPIRED,
        )

        with pytest.raises(BusinessRuleError) as exc_info:
            process_reminder(reminder, owner)

        assert exc_info.value.code == "REMINDER_STATUS_TRANSITION_INVALID"
        reminder.refresh_from_db()
        assert reminder.status == Reminder.STATUS_EXPIRED


# ---------------------------------------------------------------------------
# 8. API 层联动验证
# ---------------------------------------------------------------------------

class TestProcessReminderAPI:

    def test_process_matched_revisit_via_api(self, auth_client, _make_card):
        card, ps = _make_card()
        r1 = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=3),
        )
        r2 = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=10),
        )

        resp = auth_client(ps).post(
            f"/api/v1/reminders/{r1.id}/process/",
            {}, format="json",
        )

        assert resp.status_code == 200
        assert resp.data["status"] == Reminder.STATUS_PROCESSED

        card.refresh_from_db()
        assert card.next_remind_at == r2.remind_at

    def test_process_success_revisit_via_api(self, auth_client, _make_card):
        card, ps = _make_card(stage=MatchCard.STAGE_SUCCESS)
        r = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_SUCCESS_REVISIT,
            remind_at=timezone.now() + timedelta(days=30),
        )

        resp = auth_client(ps).post(
            f"/api/v1/reminders/{r.id}/process/",
            {}, format="json",
        )

        assert resp.status_code == 200
        assert resp.data["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" not in resp.data

    def test_process_first_meet_overdue_via_api_creates_followup(
        self, auth_client, create_customer_profile, create_staff, create_reason_enum
    ):
        owner = create_staff(name="API首见超时红娘")
        user = create_customer_profile(
            owner=owner, phone="13900100008", wechat="api_fmo",
        )
        reason = create_reason_enum(
            category=ReasonEnum.CATEGORY_OVERDUE,
            label="推荐未完成",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
            remind_at=timezone.now() - timedelta(days=1),
        )

        resp = auth_client(owner).post(
            f"/api/v1/reminders/{reminder.id}/process/",
            {
                "overdue_reason_id": reason.id,
                "overdue_reason_note": "正在补推荐",
            },
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["status"] == Reminder.STATUS_PROCESSED
        assert "created_follow_up_id" in resp.data

        followup = FollowUpRecord.objects.get(id=resp.data["created_follow_up_id"])
        assert followup.overdue_reason_id == reason.id
        assert followup.overdue_reason_note == "正在补推荐"
        assert followup.scene == FollowUpRecord.SCENE_UNMATCHED

    def test_admin_can_process_any_reminder(self, auth_client, admin_staff, create_customer_profile, create_staff):
        owner = create_staff(name="普通红娘admin")
        user = create_customer_profile(
            owner=owner, phone="13900100009", wechat="admin_process",
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() - timedelta(hours=1),
        )

        resp = auth_client(admin_staff).post(
            f"/api/v1/reminders/{reminder.id}/process/",
            {}, format="json",
        )

        assert resp.status_code == 200
        assert resp.data["status"] == Reminder.STATUS_PROCESSED
