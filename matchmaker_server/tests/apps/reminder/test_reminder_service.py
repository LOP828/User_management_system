from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import BusinessRuleError
from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.reminder.models import Reminder
from apps.reminder.services import (
    build_match_card_reminders,
    build_persisted_reminder_queryset,
    create_reminder,
    expire_target_reminders,
    process_reminder,
    refresh_match_card_next_remind_at,
)
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


@pytest.fixture
def create_match_card(create_customer_profile, create_staff):
    def factory(**kwargs):
        male_staff = kwargs.pop("male_staff", None) or create_staff(name="男方红娘")
        female_staff = kwargs.pop("female_staff", None) or create_staff(name="女方红娘")
        primary_staff = kwargs.pop("primary_staff", None) or male_staff
        suffix = f"{uuid4().int % 10**8:08d}"
        male_user = kwargs.pop(
            "male_user",
            None,
        ) or create_customer_profile(
            owner=male_staff,
            name="男方用户",
            gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}",
            wechat=f"male_service_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female_user = kwargs.pop(
            "female_user",
            None,
        ) or create_customer_profile(
            owner=female_staff,
            name="女方用户",
            gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}",
            wechat=f"female_service_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        defaults = {
            "male_user": male_user,
            "female_user": female_user,
            "male_staff": male_staff,
            "female_staff": female_staff,
            "primary_staff": primary_staff,
            "stage": MatchCard.STAGE_INITIAL_CONTACT,
            "risk_level": MatchCard.RISK_NONE,
        }
        defaults.update(kwargs)
        return MatchCard.objects.create(**defaults)

    return factory


def test_build_persisted_reminder_queryset_filters_by_role_and_query_params(
    create_customer_profile,
    create_staff,
    admin_staff,
):
    owner_a = create_staff(name="红娘A")
    owner_b = create_staff(name="红娘B")
    user_a = create_customer_profile(owner=owner_a, phone="13901000001", wechat="persisted_query_a")
    user_b = create_customer_profile(owner=owner_b, phone="13901000002", wechat="persisted_query_b")
    now = timezone.now()

    reminder_a = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user_a.id,
        staff=owner_a,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=now + timedelta(days=2),
    )
    reminder_b = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user_b.id,
        staff=owner_b,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=now + timedelta(days=1),
        status_value=Reminder.STATUS_SENT,
        is_manual=True,
    )

    own_queryset = build_persisted_reminder_queryset(owner_a, {})
    admin_filtered_queryset = build_persisted_reminder_queryset(
        admin_staff,
        {
            "staff_id": str(owner_b.id),
            "status": Reminder.STATUS_SENT,
            "target_type": Reminder.TARGET_USER,
            "remind_at_before": (now + timedelta(days=2)).isoformat(),
        },
    )

    assert list(own_queryset) == [reminder_a]
    assert list(admin_filtered_queryset) == [reminder_b]


def test_create_match_card_reminder_refreshes_next_remind_at(create_match_card):
    match_card = create_match_card()
    now = timezone.now()

    later_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        staff=match_card.primary_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=now + timedelta(days=5),
    )
    earlier_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        staff=match_card.primary_staff,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=now + timedelta(days=2),
        is_manual=True,
    )

    match_card.refresh_from_db()
    assert later_reminder.status == Reminder.STATUS_PENDING
    assert earlier_reminder.status == Reminder.STATUS_PENDING
    assert match_card.next_remind_at == earlier_reminder.remind_at


def test_create_reminder_rejects_missing_target(create_staff):
    owner = create_staff(name="不存在目标红娘")

    with pytest.raises(BusinessRuleError) as exc_info:
        create_reminder(
            target_type=Reminder.TARGET_USER,
            target_id=999999,
            staff=owner,
            remind_type=Reminder.TYPE_NORMAL,
            remind_at=timezone.now() + timedelta(hours=1),
        )

    assert exc_info.value.code == "REMINDER_TARGET_NOT_FOUND"
    assert Reminder.objects.count() == 0


def test_process_user_reminder_marks_processed_and_updates_last_action(create_customer_profile, create_staff):
    owner = create_staff(name="普通提醒红娘")
    user = create_customer_profile(owner=owner, phone="13901000003", wechat="process_user")
    baseline = user.last_unmatched_active_at
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=timezone.now() + timedelta(hours=2),
    )

    result = process_reminder(reminder, owner)

    reminder.refresh_from_db()
    user.refresh_from_db()
    assert result["id"] == reminder.id
    assert result["status"] == Reminder.STATUS_PROCESSED
    assert result["processed_at"] is not None
    assert reminder.status == Reminder.STATUS_PROCESSED
    assert reminder.processed_at is not None
    assert user.last_action_at is not None
    assert user.last_unmatched_active_at == baseline


def test_process_first_meet_overdue_requires_valid_reason(create_customer_profile, create_staff):
    owner = create_staff(name="超时提醒红娘")
    user = create_customer_profile(owner=owner, phone="13901000004", wechat="overdue_missing_reason")
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
        remind_at=timezone.now() - timedelta(days=1),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        process_reminder(reminder, owner)

    reminder.refresh_from_db()
    assert exc_info.value.code == "OVERDUE_REASON_REQUIRED"
    assert reminder.status == Reminder.STATUS_PENDING
    assert FollowUpRecord.objects.filter(user=user, scene=FollowUpRecord.SCENE_UNMATCHED).count() == 0


def test_process_first_meet_overdue_creates_followup_and_updates_user(
    create_customer_profile,
    create_staff,
    create_reason_enum,
):
    owner = create_staff(name="超时处理红娘")
    user = create_customer_profile(owner=owner, phone="13901000005", wechat="overdue_with_reason")
    overdue_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_OVERDUE,
        label="库存不足",
    )
    previous_baseline = user.last_unmatched_active_at
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
        remind_at=timezone.now() - timedelta(days=1),
    )

    result = process_reminder(
        reminder,
        owner,
        overdue_reason=overdue_reason,
        overdue_reason_note="已重新安排推荐计划",
    )

    reminder.refresh_from_db()
    user.refresh_from_db()
    follow_up = FollowUpRecord.objects.get(id=result["created_follow_up_id"])
    assert reminder.status == Reminder.STATUS_PROCESSED
    assert follow_up.scene == FollowUpRecord.SCENE_UNMATCHED
    assert follow_up.user_id == user.id
    assert follow_up.staff_id == owner.id
    assert follow_up.overdue_reason_id == overdue_reason.id
    assert follow_up.overdue_reason_note == "已重新安排推荐计划"
    assert user.last_action_at is not None
    assert user.last_unmatched_active_at is not None
    assert user.last_unmatched_active_at >= previous_baseline


def test_process_reminder_rejects_non_receiver(create_customer_profile, create_staff):
    owner = create_staff(name="提醒接收人")
    other_staff = create_staff(name="无关红娘")
    user = create_customer_profile(owner=owner, phone="13901000006", wechat="process_permission")
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_NORMAL,
        remind_at=timezone.now() + timedelta(hours=1),
    )

    with pytest.raises(PermissionDenied):
        process_reminder(reminder, other_staff)

    reminder.refresh_from_db()
    assert reminder.status == Reminder.STATUS_PENDING


def test_expire_target_reminders_only_touches_matching_active_rows_and_refreshes_next_remind_at(create_match_card):
    match_card = create_match_card()
    unrelated_card = create_match_card()
    now = timezone.now()

    matched_revisit = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        staff=match_card.primary_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=now + timedelta(days=5),
    )
    success_revisit = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        staff=match_card.primary_staff,
        remind_type=Reminder.TYPE_SUCCESS_REVISIT,
        remind_at=now + timedelta(days=3),
        status_value=Reminder.STATUS_SENT,
    )
    manual_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        staff=match_card.primary_staff,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=now + timedelta(days=1),
        is_manual=True,
    )
    processed_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=match_card.id,
        staff=match_card.primary_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=now + timedelta(days=7),
        status_value=Reminder.STATUS_PROCESSED,
    )
    unrelated_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=unrelated_card.id,
        staff=unrelated_card.primary_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=now + timedelta(days=4),
    )

    updated = expire_target_reminders(
        Reminder.TARGET_MATCH_CARD,
        match_card.id,
        remind_types=[Reminder.TYPE_MANUAL, Reminder.TYPE_SUCCESS_REVISIT],
    )

    match_card.refresh_from_db()
    unrelated_card.refresh_from_db()
    matched_revisit.refresh_from_db()
    success_revisit.refresh_from_db()
    manual_reminder.refresh_from_db()
    processed_reminder.refresh_from_db()
    unrelated_reminder.refresh_from_db()
    assert updated == 2
    assert matched_revisit.status == Reminder.STATUS_PENDING
    assert success_revisit.status == Reminder.STATUS_EXPIRED
    assert manual_reminder.status == Reminder.STATUS_EXPIRED
    assert processed_reminder.status == Reminder.STATUS_PROCESSED
    assert unrelated_reminder.status == Reminder.STATUS_PENDING
    assert match_card.next_remind_at == matched_revisit.remind_at
    assert unrelated_card.next_remind_at == unrelated_reminder.remind_at


def test_refresh_match_card_next_remind_at_falls_back_to_derived_logic_when_no_persisted_rows(create_match_card):
    match_card = create_match_card()
    expected = min(item["remind_at"] for item in build_match_card_reminders(match_card))

    next_remind_at = refresh_match_card_next_remind_at(match_card)

    match_card.refresh_from_db()
    assert next_remind_at == expected
    assert match_card.next_remind_at == expected
