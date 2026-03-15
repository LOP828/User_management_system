from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.reminder.models import Reminder
from apps.reminder.services import create_reminder
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
            wechat=f"male_user_{suffix}",
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
            wechat=f"female_user_{suffix}",
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


def test_matchmaker_only_sees_own_derived_reminders(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘A")
    female_staff = create_staff(name="女方红娘A")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    response = auth_client(male_staff).get("/api/v1/reminders/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    item = response.data["results"][0]
    assert item["target_type"] == "match_card"
    assert item["target_id"] == card.id
    assert item["staff_id"] == male_staff.id
    assert item["remind_type"] == "matched_revisit"


def test_admin_can_view_all_and_filter_by_staff_id(auth_client, admin_staff, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘B")
    female_staff = create_staff(name="女方红娘B")
    create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    all_response = auth_client(admin_staff).get("/api/v1/reminders/")
    filtered_response = auth_client(admin_staff).get(f"/api/v1/reminders/?staff_id={female_staff.id}")

    assert all_response.status_code == 200
    assert all_response.data["count"] == 2
    assert filtered_response.status_code == 200
    assert filtered_response.data["count"] == 1
    assert filtered_response.data["results"][0]["staff_id"] == female_staff.id


def test_reminder_list_marks_overdue_in_target_summary(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘C")
    female_staff = create_staff(name="女方红娘C")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)
    old_created_at = timezone.now() - timedelta(days=10)
    MatchCard.objects.filter(pk=card.pk).update(created_at=old_created_at, next_remind_at=old_created_at + timedelta(days=7))

    response = auth_client(male_staff).get("/api/v1/reminders/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert "已逾期" in response.data["results"][0]["target_summary"]


def test_manual_followup_changes_derived_reminder(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘D")
    female_staff = create_staff(name="女方红娘D")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    followup_response = auth_client(male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "男方手动约下次回访",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "manual",
            "next_remind_at": "2026-03-18T09:00:00Z",
        },
        format="json",
    )

    assert followup_response.status_code == 201

    reminder_response = auth_client(male_staff).get("/api/v1/reminders/")

    assert reminder_response.status_code == 200
    assert reminder_response.data["count"] == 1
    item = reminder_response.data["results"][0]
    assert item["is_manual"] is True
    assert item["remind_at"].startswith("2026-03-18T17:00:00+08:00")


def test_status_and_target_type_filters_apply_to_derived_reminders(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘E")
    female_staff = create_staff(name="女方红娘E")
    create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    pending_response = auth_client(male_staff).get("/api/v1/reminders/?status=pending&target_type=match_card")
    processed_response = auth_client(male_staff).get("/api/v1/reminders/?status=processed")

    assert pending_response.status_code == 200
    assert pending_response.data["count"] == 1
    assert processed_response.status_code == 200
    assert processed_response.data["count"] == 0


def test_receiver_can_process_persisted_reminder(auth_client, create_customer_profile, create_staff):
    owner = create_staff(name="处理提醒红娘")
    user = create_customer_profile(owner=owner, phone="13902000001", wechat="reminder_process_ok")
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=timezone.now() + timedelta(hours=2),
    )

    response = auth_client(owner).post(
        f"/api/v1/reminders/{reminder.id}/process/",
        {},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["id"] == reminder.id
    assert response.data["status"] == Reminder.STATUS_PROCESSED
    assert response.data["processed_at"]
    reminder.refresh_from_db()
    user.refresh_from_db()
    assert reminder.status == Reminder.STATUS_PROCESSED
    assert reminder.processed_at is not None
    assert user.last_action_at is not None


def test_non_receiver_cannot_process_persisted_reminder(
    auth_client,
    create_customer_profile,
    create_staff,
):
    owner = create_staff(name="提醒接收红娘")
    other_staff = create_staff(name="无权限处理红娘")
    user = create_customer_profile(owner=owner, phone="13902000002", wechat="reminder_process_denied")
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_NORMAL,
        remind_at=timezone.now() + timedelta(hours=1),
    )

    response = auth_client(other_staff).post(
        f"/api/v1/reminders/{reminder.id}/process/",
        {},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"
    reminder.refresh_from_db()
    assert reminder.status == Reminder.STATUS_PENDING


def test_processed_reminder_cannot_be_processed_again(auth_client, create_customer_profile, create_staff):
    owner = create_staff(name="重复处理红娘")
    user = create_customer_profile(owner=owner, phone="13902000003", wechat="reminder_process_invalid_status")
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=timezone.now() + timedelta(hours=1),
        status_value=Reminder.STATUS_PROCESSED,
    )

    response = auth_client(owner).post(
        f"/api/v1/reminders/{reminder.id}/process/",
        {},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "REMINDER_STATUS_TRANSITION_INVALID"
    reminder.refresh_from_db()
    assert reminder.status == Reminder.STATUS_PROCESSED


def test_first_meet_overdue_process_requires_overdue_reason(
    auth_client,
    create_customer_profile,
    create_staff,
):
    owner = create_staff(name="未首见处理红娘")
    user = create_customer_profile(owner=owner, phone="13902000004", wechat="reminder_first_meet_overdue")
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
        remind_at=timezone.now() - timedelta(days=1),
    )

    response = auth_client(owner).post(
        f"/api/v1/reminders/{reminder.id}/process/",
        {},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "OVERDUE_REASON_REQUIRED"
    reminder.refresh_from_db()
    assert reminder.status == Reminder.STATUS_PENDING
    assert FollowUpRecord.objects.filter(user=user, scene=FollowUpRecord.SCENE_UNMATCHED).count() == 0


def test_first_meet_overdue_process_accepts_valid_reason(
    auth_client,
    create_customer_profile,
    create_staff,
    create_reason_enum,
):
    owner = create_staff(name="未首见闭环红娘")
    user = create_customer_profile(owner=owner, phone="13902000005", wechat="reminder_first_meet_reason")
    overdue_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_OVERDUE,
        label="库存不足",
    )
    reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FIRST_MEET_OVERDUE,
        remind_at=timezone.now() - timedelta(days=1),
    )

    response = auth_client(owner).post(
        f"/api/v1/reminders/{reminder.id}/process/",
        {
            "overdue_reason_id": overdue_reason.id,
            "overdue_reason_note": "已重新安排推荐计划",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == Reminder.STATUS_PROCESSED
    assert "created_follow_up_id" in response.data
    reminder.refresh_from_db()
    follow_up = FollowUpRecord.objects.get(id=response.data["created_follow_up_id"])
    assert reminder.status == Reminder.STATUS_PROCESSED
    assert follow_up.user_id == user.id
    assert follow_up.overdue_reason_id == overdue_reason.id
