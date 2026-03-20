"""边界测试：ended 配对卡上的残留 reminder 不允许继续 process。"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.reminder.models import Reminder
from apps.reminder.services import create_reminder, process_reminder
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


@pytest.fixture
def _make_ended_card(create_customer_profile, create_staff):
    def factory(*, primary_staff=None):
        ps = primary_staff or create_staff(name="主操作红娘")
        suffix = f"{uuid4().int % 10**8:08d}"
        male = create_customer_profile(
            owner=ps,
            name="男方",
            gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}",
            wechat=f"m_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=False,
        )
        female = create_customer_profile(
            owner=ps,
            name="女方",
            gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}",
            wechat=f"f_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=False,
        )
        card = MatchCard.objects.create(
            male_user=male,
            female_user=female,
            male_staff=ps,
            female_staff=ps,
            primary_staff=ps,
            stage=MatchCard.STAGE_ENDED,
            risk_level=MatchCard.RISK_NONE,
            ended_at=timezone.now(),
            next_remind_at=None,
        )
        return card, ps

    return factory


class TestProcessReminderOnEndedCard:

    @pytest.mark.parametrize(
        ("remind_type", "is_manual"),
        [
            (Reminder.TYPE_MATCHED_REVISIT, False),
            (Reminder.TYPE_MANUAL, True),
            (Reminder.TYPE_SUCCESS_REVISIT, False),
        ],
    )
    def test_match_card_reminder_on_ended_card_is_blocked(
        self,
        _make_ended_card,
        remind_type,
        is_manual,
    ):
        card, ps = _make_ended_card()
        male_before = card.male_user.last_action_at
        female_before = card.female_user.last_action_at
        reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=remind_type,
            remind_at=timezone.now() + timedelta(days=7),
            is_manual=is_manual,
        )

        with pytest.raises(BusinessRuleError) as exc_info:
            process_reminder(reminder, ps)

        assert exc_info.value.code == "MATCH_STAGE_TRANSITION_INVALID"

        reminder.refresh_from_db()
        card.refresh_from_db()
        card.male_user.refresh_from_db()
        card.female_user.refresh_from_db()

        assert reminder.status == Reminder.STATUS_PENDING
        assert reminder.processed_at is None
        assert card.next_remind_at == reminder.remind_at
        assert card.male_user.last_action_at == male_before
        assert card.female_user.last_action_at == female_before

    def test_first_meet_overdue_on_ended_card_is_blocked_without_followup(
        self,
        _make_ended_card,
        create_reason_enum,
    ):
        card, ps = _make_ended_card()
        reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
            remind_at=timezone.now() - timedelta(hours=1),
        )
        overdue_reason = create_reason_enum(
            label="历史残留",
            category=ReasonEnum.CATEGORY_OVERDUE,
        )

        with pytest.raises(BusinessRuleError) as exc_info:
            process_reminder(reminder, ps, overdue_reason=overdue_reason)

        assert exc_info.value.code == "MATCH_STAGE_TRANSITION_INVALID"

        reminder.refresh_from_db()
        assert reminder.status == Reminder.STATUS_PENDING
        assert reminder.processed_at is None
        assert FollowUpRecord.objects.filter(match_card=card).count() == 0
        assert FollowUpRecord.objects.filter(user__in=[card.male_user, card.female_user]).count() == 0


class TestProcessReminderOtherTargetsUnaffected:

    @pytest.mark.parametrize(
        "stage",
        [MatchCard.STAGE_INITIAL_CONTACT, MatchCard.STAGE_STABLE_CONTACT],
    )
    def test_non_ended_match_card_reminder_still_processes(self, create_customer_profile, create_staff, stage):
        ps = create_staff(name="正常配对卡红娘")
        suffix = f"{uuid4().int % 10**8:08d}"
        male = create_customer_profile(
            owner=ps,
            name="男方",
            gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}",
            wechat=f"m_ok_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female = create_customer_profile(
            owner=ps,
            name="女方",
            gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}",
            wechat=f"f_ok_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        card = MatchCard.objects.create(
            male_user=male,
            female_user=female,
            male_staff=ps,
            female_staff=ps,
            primary_staff=ps,
            stage=stage,
            risk_level=MatchCard.RISK_NONE,
        )
        reminder = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=7),
        )

        result = process_reminder(reminder, ps)

        assert result["status"] == Reminder.STATUS_PROCESSED
        reminder.refresh_from_db()
        assert reminder.processed_at is not None

    def test_user_target_reminder_still_processes(self, create_customer_profile, create_staff):
        owner = create_staff(name="用户提醒红娘")
        user = create_customer_profile(
            owner=owner,
            phone="13900109999",
            wechat="user_target_ok",
        )
        baseline = user.last_action_at
        reminder = create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
            staff=owner,
            remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
            remind_at=timezone.now() - timedelta(hours=1),
        )

        result = process_reminder(reminder, owner)

        assert result["status"] == Reminder.STATUS_PROCESSED
        reminder.refresh_from_db()
        user.refresh_from_db()
        assert reminder.processed_at is not None
        assert user.last_action_at is not None
        if baseline is not None:
            assert user.last_action_at >= baseline


class TestEndMatchCardExpiresReminders:

    def test_end_match_card_expires_all_active_reminders(
        self,
        auth_client,
        create_customer_profile,
        create_staff,
    ):
        ps = create_staff(name="结束测试红娘")
        suffix = f"{uuid4().int % 10**8:08d}"
        male = create_customer_profile(
            owner=ps,
            name="男方",
            gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}",
            wechat=f"m_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female = create_customer_profile(
            owner=ps,
            name="女方",
            gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}",
            wechat=f"f_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        card = MatchCard.objects.create(
            male_user=male,
            female_user=female,
            male_staff=ps,
            female_staff=ps,
            primary_staff=ps,
            stage=MatchCard.STAGE_INITIAL_CONTACT,
            risk_level=MatchCard.RISK_NONE,
        )

        mr = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MATCHED_REVISIT,
            remind_at=timezone.now() + timedelta(days=7),
        )
        manual = create_reminder(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            staff=ps,
            remind_type=Reminder.TYPE_MANUAL,
            remind_at=timezone.now() + timedelta(days=2),
            is_manual=True,
        )

        resp = auth_client(ps).post(
            f"/api/v1/match-cards/{card.id}/end/",
            {"end_reason_staff": "双方不合适"},
            format="json",
        )
        assert resp.status_code == 200

        mr.refresh_from_db()
        manual.refresh_from_db()
        card.refresh_from_db()
        assert mr.status == Reminder.STATUS_EXPIRED
        assert manual.status == Reminder.STATUS_EXPIRED
        assert card.next_remind_at is None

        active_count = Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=card.id,
            status__in=[Reminder.STATUS_PENDING, Reminder.STATUS_SENT],
        ).count()
        assert active_count == 0
