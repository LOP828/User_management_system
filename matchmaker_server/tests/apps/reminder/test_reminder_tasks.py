"""
测试 reminder 定时任务扫描逻辑（直接调用 service 函数，不依赖真实 Celery/Redis）。
涵盖：
  - scan_followup_timeout_reminders（BR-REMIND-009）
  - scan_first_meet_reminders（BR-REMIND-001）
  - scan_pause_revisit_reminders（BR-REMIND-002）
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.reminder.models import Reminder
from apps.reminder.services import (
    scan_first_meet_reminders,
    scan_followup_timeout_reminders,
    scan_pause_revisit_reminders,
)
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

    def test_skips_user_with_existing_match_card_as_male(
        self, create_customer_profile, create_staff, matchmaker_staff
    ):
        """曾作为男方建过卡的用户不再生成 first_meet 提醒"""
        female_owner = create_staff(phone="13800138901", name="女方红娘FM1")
        male_user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=5),
        )
        female_user = create_customer_profile(
            owner=female_owner,
            gender=CustomerProfile.GENDER_FEMALE,
            phone="13900139901",
        )
        MatchCard.objects.create(
            male_user=male_user,
            female_user=female_user,
            male_staff=matchmaker_staff,
            female_staff=female_owner,
            primary_staff=matchmaker_staff,
            stage=MatchCard.STAGE_ENDED,
        )

        count = scan_first_meet_reminders()

        assert count == 0
        assert not Reminder.objects.filter(target_id=male_user.id).exists()

    def test_skips_user_with_existing_match_card_as_female(
        self, create_customer_profile, create_staff, matchmaker_staff
    ):
        """曾作为女方建过卡的用户不再生成 first_meet 提醒"""
        male_owner = create_staff(phone="13800138902", name="男方红娘FM2")
        female_user = create_customer_profile(
            owner=matchmaker_staff,
            gender=CustomerProfile.GENDER_FEMALE,
            phone="13900139902",
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=3),
        )
        male_user = create_customer_profile(
            owner=male_owner,
            phone="13900139903",
        )
        MatchCard.objects.create(
            male_user=male_user,
            female_user=female_user,
            male_staff=male_owner,
            female_staff=matchmaker_staff,
            primary_staff=male_owner,
            stage=MatchCard.STAGE_ENDED,
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_skips_reflowed_user_with_match_card_history(
        self, create_customer_profile, create_staff, matchmaker_staff
    ):
        """
        已回流用户（曾有 MatchCard，现在回到 communicated_pending_recommend）
        不应再收到 first_meet 提醒。
        """
        female_owner = create_staff(phone="13800138903", name="女方红娘FM3")
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            is_in_match=False,
            paid_at=timezone.now() - timedelta(days=5),
        )
        partner = create_customer_profile(
            owner=female_owner,
            gender=CustomerProfile.GENDER_FEMALE,
            phone="13900139904",
            is_in_match=False,
        )
        # 曾建卡 → 已结束 → 回流
        MatchCard.objects.create(
            male_user=user,
            female_user=partner,
            male_staff=matchmaker_staff,
            female_staff=female_owner,
            primary_staff=matchmaker_staff,
            stage=MatchCard.STAGE_ENDED,
        )

        count = scan_first_meet_reminders()

        assert count == 0

    def test_generates_for_user_without_any_match_card(
        self, create_customer_profile, matchmaker_staff
    ):
        """从未建过卡的用户正常生成 first_meet 提醒"""
        user = create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paid_at=timezone.now() - timedelta(days=3),
        )
        # 不创建任何 MatchCard

        count = scan_first_meet_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_FIRST_MEET_DELAYED


# ---------------------------------------------------------------------------
# BR-REMIND-002：scan_pause_revisit_reminders
# ---------------------------------------------------------------------------


class TestPauseRevisitReminders:

    def test_creates_reminder_when_paused_at_exceeds_interval(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """暂停超过 pause_revisit_days 天 → 生成 pause_revisit 提醒"""
        pl = create_payment_level(pause_revisit_days=30)
        user = create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=31),
        )

        count = scan_pause_revisit_reminders()

        assert count == 1
        r = Reminder.objects.get(target_id=user.id)
        assert r.remind_type == Reminder.TYPE_PAUSE_REVISIT
        assert r.staff_id == matchmaker_staff.id
        assert r.status == Reminder.STATUS_PENDING

    def test_skips_when_paused_at_within_interval(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """暂停未满 pause_revisit_days → 不生成提醒"""
        pl = create_payment_level(pause_revisit_days=30)
        create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=10),
        )

        count = scan_pause_revisit_reminders()

        assert count == 0

    def test_skips_when_paused_at_is_null(
        self, create_customer_profile, matchmaker_staff
    ):
        """paused_at 为 NULL（存量数据）→ 跳过不报错"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=None,
        )

        count = scan_pause_revisit_reminders()

        assert count == 0

    def test_baseline_falls_back_to_latest_unmatched_followup(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """有 unmatched 跟进记录时，基线回退到 follow_up.created_at"""
        pl = create_payment_level(pause_revisit_days=30)
        user = create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=60),
        )
        # 10 天前有跟进记录 → 基线变成 10 天前，不满 30 天 → 不生成
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            staff=matchmaker_staff,
            content="暂停期间回访",
        )
        # 手动把 created_at 改到 10 天前
        FollowUpRecord.objects.filter(user=user).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        count = scan_pause_revisit_reminders()

        assert count == 0

    def test_baseline_followup_exceeds_interval_generates_reminder(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """最近跟进超过 interval 天 → 生成提醒"""
        pl = create_payment_level(pause_revisit_days=30)
        user = create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=60),
        )
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            staff=matchmaker_staff,
            content="暂停期间回访",
        )
        FollowUpRecord.objects.filter(user=user).update(
            created_at=timezone.now() - timedelta(days=35)
        )

        count = scan_pause_revisit_reminders()

        assert count == 1

    def test_idempotent_same_day_no_duplicate(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """同日重复扫描不重复创建"""
        pl = create_payment_level(pause_revisit_days=30)
        create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=31),
        )

        count1 = scan_pause_revisit_reminders()
        count2 = scan_pause_revisit_reminders()

        assert count1 == 1
        assert count2 == 0

    def test_skips_non_paused_users(
        self, create_customer_profile, matchmaker_staff
    ):
        """非暂停状态的用户不触发 pause_revisit"""
        create_customer_profile(
            owner=matchmaker_staff,
            pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
            paused_at=timezone.now() - timedelta(days=60),
        )

        count = scan_pause_revisit_reminders()

        assert count == 0

    def test_skips_deleted_users(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """已软删除用户不触发 pause_revisit"""
        pl = create_payment_level(pause_revisit_days=30)
        create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=31),
            deleted_at=timezone.now(),
        )

        count = scan_pause_revisit_reminders()

        assert count == 0

    # ── baseline bug 修复覆盖 ─────────────────────────────────────────────

    def test_pre_pause_followup_not_used_as_baseline(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """暂停前的 unmatched 跟进不应作为 baseline，应回退到 paused_at。

        场景：paused_at=31天前，跟进记录 created_at=40天前（早于暂停）。
        baseline 应为 paused_at(31天前)，超过 30 天 → 生成提醒。
        """
        pl = create_payment_level(pause_revisit_days=30)
        user = create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=31),
        )
        # 暂停前的跟进记录（created_at 早于 paused_at）
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            staff=matchmaker_staff,
            content="暂停前的跟进",
        )
        FollowUpRecord.objects.filter(user=user).update(
            created_at=timezone.now() - timedelta(days=40)
        )

        count = scan_pause_revisit_reminders()

        # baseline = paused_at(31天前) → 超过 30 天 → 应生成
        assert count == 1

    def test_post_pause_followup_used_as_baseline(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """暂停后的 unmatched 跟进应优先作为 baseline。

        场景：paused_at=60天前，暂停后跟进 created_at=10天前。
        baseline 应为跟进(10天前)，未满 30 天 → 不生成提醒。
        """
        pl = create_payment_level(pause_revisit_days=30)
        user = create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=60),
        )
        # 暂停后的跟进记录
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            staff=matchmaker_staff,
            content="暂停后回访",
        )
        FollowUpRecord.objects.filter(user=user).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        count = scan_pause_revisit_reminders()

        # baseline = 跟进(10天前) → 未满 30 天 → 不生成
        assert count == 0

    def test_pre_pause_followup_ignored_falls_back_to_paused_at(
        self, create_customer_profile, matchmaker_staff, create_payment_level
    ):
        """仅有暂停前跟进、无暂停后跟进时，正确回退到 paused_at。

        场景：paused_at=20天前，跟进 created_at=50天前。
        baseline 应为 paused_at(20天前)，未满 30 天 → 不生成提醒。
        若 bug 仍在（误用暂停前跟进 50天前做 baseline），则会错误生成。
        """
        pl = create_payment_level(pause_revisit_days=30)
        user = create_customer_profile(
            owner=matchmaker_staff,
            payment_level=pl,
            pool_status=CustomerProfile.STATUS_PAUSED,
            pre_pause_status=CustomerProfile.STATUS_NEW_PENDING,
            paused_at=timezone.now() - timedelta(days=20),
        )
        # 仅有暂停前的跟进
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            staff=matchmaker_staff,
            content="暂停前的旧跟进",
        )
        FollowUpRecord.objects.filter(user=user).update(
            created_at=timezone.now() - timedelta(days=50)
        )

        count = scan_pause_revisit_reminders()

        # baseline = paused_at(20天前) → 未满 30 天 → 不生成
        # 若误用暂停前跟进(50天前)做 baseline → 会错误生成提醒
        assert count == 0
