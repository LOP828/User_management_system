"""
测试 reminder 定时任务扫描逻辑（直接调用 service 函数，不依赖真实 Celery/Redis）。
涵盖：
  - scan_followup_timeout_reminders（BR-REMIND-009）
  - scan_first_meet_reminders（BR-REMIND-001）
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reminder.models import Reminder
from apps.reminder.services import scan_first_meet_reminders, scan_followup_timeout_reminders
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_user(create_customer_profile, create_payment_level, owner, **kwargs):
    """创建带 payment_level 的 CustomerProfile，last_unmatched_active_at = created_at（conftest 默认行为）。"""
    pl = kwargs.pop("payment_level", None) or create_payment_level()
    return create_customer_profile(owner=owner, payment_level=pl, **kwargs)


# ---------------------------------------------------------------------------
# BR-REMIND-009：scan_followup_timeout_reminders
# ---------------------------------------------------------------------------


class TestScanFollowupTimeout:
    """BR-REMIND-009：未配对跟进超时提醒扫描"""

    def test_creates_reminder_when_overdue(self, create_customer_profile, create_payment_level, matchmaker_staff):
        """超时用户生成 followup_timeout 提醒"""
        pl = create_payment_level(followup_timeout_days=7)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        )
        # 把 last_unmatched_active_at 设为 8 天前（超时）
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=timezone.now() - timedelta(days=8)
        )

        count = scan_followup_timeout_reminders()

        assert count == 1
        reminder = Reminder.objects.get(target_type=Reminder.TARGET_USER, target_id=user.id)
        assert reminder.remind_type == Reminder.TYPE_FOLLOWUP_TIMEOUT
        assert reminder.status == Reminder.STATUS_PENDING
        assert reminder.staff_id == matchmaker_staff.id
        assert reminder.is_manual is False

    def test_no_reminder_when_within_timeout(self, create_customer_profile, create_payment_level, matchmaker_staff):
        """未超时用户不生成提醒"""
        pl = create_payment_level(followup_timeout_days=7)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        )
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=timezone.now() - timedelta(days=3)
        )

        count = scan_followup_timeout_reminders()

        assert count == 0
        assert not Reminder.objects.filter(target_id=user.id, remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT).exists()

    def test_skips_paused_users(self, create_customer_profile, create_payment_level, matchmaker_staff):
        """暂停用户不生成提醒"""
        pl = create_payment_level(followup_timeout_days=1)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
        )
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=timezone.now() - timedelta(days=30)
        )

        count = scan_followup_timeout_reminders()

        assert count == 0

    def test_skips_met_not_continue(self, create_customer_profile, create_payment_level, matchmaker_staff):
        """已见面未继续用户不生成提醒"""
        pl = create_payment_level(followup_timeout_days=1)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_MET_NOT_CONTINUE,
        )
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=timezone.now() - timedelta(days=30)
        )

        count = scan_followup_timeout_reminders()

        assert count == 0

    def test_skips_in_match_users(self, create_customer_profile, create_payment_level, matchmaker_staff):
        """配对中用户不生成提醒"""
        pl = create_payment_level(followup_timeout_days=1)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=timezone.now() - timedelta(days=30)
        )

        count = scan_followup_timeout_reminders()

        assert count == 0

    def test_idempotent_skips_if_already_today(self, create_customer_profile, create_payment_level, matchmaker_staff):
        """当日已有 followup_timeout 提醒则不重复生成"""
        pl = create_payment_level(followup_timeout_days=7)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        )
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=timezone.now() - timedelta(days=10)
        )

        count1 = scan_followup_timeout_reminders()
        count2 = scan_followup_timeout_reminders()

        assert count1 == 1
        assert count2 == 0
        assert Reminder.objects.filter(target_id=user.id, remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT).count() == 1

    def test_uses_created_at_as_fallback_when_no_unmatched_active_at(
        self, create_customer_profile, create_payment_level, matchmaker_staff
    ):
        """last_unmatched_active_at 为 NULL 时以 created_at 为基准"""
        pl = create_payment_level(followup_timeout_days=7)
        user = _make_user(
            create_customer_profile, create_payment_level, matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_NEW_PENDING,
            last_unmatched_active_at=None,
        )
        # 把 created_at 设为 10 天前（SQLite 不支持 update auto_now，直接用 filter+update）
        CustomerProfile.objects.filter(pk=user.pk).update(
            last_unmatched_active_at=None,
            created_at=timezone.now() - timedelta(days=10),
        )

        count = scan_followup_timeout_reminders()

        assert count == 1


# ---------------------------------------------------------------------------
# BR-REMIND-001：scan_first_meet_reminders
# ---------------------------------------------------------------------------


class TestScanFirstMeet:
    """BR-REMIND-001：未首见进度提醒扫描"""

    def test_day2_creates_first_meet_pending(self, create_customer_profile, matchmaker_staff):
        """付费 2 天，生成 first_meet_pending"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=2),
        )

        count = scan_first_meet_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_FIRST_MEET_PENDING

    def test_day3_creates_first_meet_delayed(self, create_customer_profile, matchmaker_staff):
        """付费 3 天，生成 first_meet_delayed"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=3),
        )

        count = scan_first_meet_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_FIRST_MEET_DELAYED

    def test_day4_creates_first_meet_warning(self, create_customer_profile, matchmaker_staff):
        """付费 4 天，生成 first_meet_warning"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=4),
        )

        count = scan_first_meet_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_FIRST_MEET_WARNING

    def test_day5_creates_first_meet_overdue(self, create_customer_profile, matchmaker_staff):
        """付费 5 天，生成 first_meet_overdue"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=5),
        )

        count = scan_first_meet_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_FIRST_MEET_OVERDUE

    def test_day1_creates_normal(self, create_customer_profile, matchmaker_staff):
        """付费 1 天，生成 normal 提醒"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=1),
        )

        count = scan_first_meet_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_NORMAL

    def test_day0_no_reminder(self, create_customer_profile, matchmaker_staff):
        """付费不足 1 天，不生成提醒"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(hours=12),
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_skips_no_paid_at(self, create_customer_profile, matchmaker_staff):
        """paid_at 为空的用户不生成提醒"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_skips_paused(self, create_customer_profile, matchmaker_staff):
        """暂停用户不生成提醒"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_PAUSED,
            paid_at=timezone.now() - timedelta(days=5),
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_skips_met_not_continue(self, create_customer_profile, matchmaker_staff):
        """已见面未继续用户不生成提醒"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_MET_NOT_CONTINUE,
            paid_at=timezone.now() - timedelta(days=5),
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_skips_in_match(self, create_customer_profile, matchmaker_staff):
        """配对中用户不生成提醒"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
            paid_at=timezone.now() - timedelta(days=5),
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_idempotent_active_reminder_skipped(self, create_customer_profile, matchmaker_staff):
        """已有 active 的同类型提醒则不重复生成"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=3),
        )

        count1 = scan_first_meet_reminders()
        count2 = scan_first_meet_reminders()

        assert count1 == 1
        assert count2 == 0
        assert Reminder.objects.filter(target_id=user.id).count() == 1

    def test_higher_threshold_takes_priority(self, create_customer_profile, matchmaker_staff):
        """付费 5 天只生成 overdue，不生成低级别提醒"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=5),
        )

        scan_first_meet_reminders()

        reminders = list(Reminder.objects.filter(target_id=user.id).values_list("remind_type", flat=True))
        assert reminders == [Reminder.TYPE_FIRST_MEET_OVERDUE]

    def test_reminder_fields(self, create_customer_profile, matchmaker_staff):
        """检查生成提醒的字段正确性"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=2),
        )

        scan_first_meet_reminders()

        r = Reminder.objects.get(target_id=user.id)
        assert r.target_type == Reminder.TARGET_USER
        assert r.staff_id == matchmaker_staff.id
        assert r.status == Reminder.STATUS_PENDING
        assert r.is_manual is False
