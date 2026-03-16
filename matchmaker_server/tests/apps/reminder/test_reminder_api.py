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


def test_matchmaker_only_sees_own_persisted_reminders(auth_client, create_customer_profile, create_staff):
    owner_a = create_staff(name="提醒红娘A")
    owner_b = create_staff(name="提醒红娘B")
    user_a = create_customer_profile(owner=owner_a, phone="13902001001", wechat="persisted_list_a")
    user_b = create_customer_profile(owner=owner_b, phone="13902001002", wechat="persisted_list_b")
    own_reminder = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user_a.id,
        staff=owner_a,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=timezone.now() + timedelta(hours=2),
    )
    create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user_b.id,
        staff=owner_b,
        remind_type=Reminder.TYPE_NORMAL,
        remind_at=timezone.now() + timedelta(hours=3),
    )

    response = auth_client(owner_a).get("/api/v1/reminders/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    item = response.data["results"][0]
    assert item["id"] == own_reminder.id
    assert item["target_type"] == Reminder.TARGET_USER
    assert item["target_id"] == user_a.id
    assert item["target_name"] == user_a.name
    assert item["staff_id"] == owner_a.id
    assert item["remind_type"] == Reminder.TYPE_FOLLOWUP_TIMEOUT


def test_matched_revisit_created_via_match_card_api_appears_in_persisted_list(
    auth_client,
    create_customer_profile,
    create_staff,
):
    male_staff = create_staff(name="配对提醒男方A")
    female_staff = create_staff(name="配对提醒女方A")
    male_user = create_customer_profile(
        owner=male_staff,
        name="配对男方A",
        gender=CustomerProfile.GENDER_MALE,
        phone="13902001101",
        wechat="matched_reminder_male_a",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        name="配对女方A",
        gender=CustomerProfile.GENDER_FEMALE,
        phone="13902001102",
        wechat="matched_reminder_female_a",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )

    create_response = auth_client(male_staff).post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": 1,
        },
        format="json",
    )
    assert create_response.status_code == 201

    male_response = auth_client(male_staff).get("/api/v1/reminders/?remind_type=matched_revisit")
    female_response = auth_client(female_staff).get("/api/v1/reminders/?remind_type=matched_revisit")

    assert male_response.status_code == 200
    assert male_response.data["count"] == 1
    assert male_response.data["results"][0]["target_type"] == Reminder.TARGET_MATCH_CARD
    assert male_response.data["results"][0]["target_id"] == create_response.data["id"]
    assert male_response.data["results"][0]["staff_id"] == male_staff.id
    assert male_response.data["results"][0]["remind_type"] == Reminder.TYPE_MATCHED_REVISIT
    assert female_response.status_code == 200
    assert female_response.data["count"] == 1
    assert female_response.data["results"][0]["staff_id"] == female_staff.id
    assert female_response.data["results"][0]["remind_type"] == Reminder.TYPE_MATCHED_REVISIT


def test_admin_can_view_all_and_filter_by_staff_id(auth_client, admin_staff, create_customer_profile, create_staff):
    owner_a = create_staff(name="提醒红娘C")
    owner_b = create_staff(name="提醒红娘D")
    user_a = create_customer_profile(owner=owner_a, phone="13902001003", wechat="persisted_admin_a")
    user_b = create_customer_profile(owner=owner_b, phone="13902001004", wechat="persisted_admin_b")
    create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user_a.id,
        staff=owner_a,
        remind_type=Reminder.TYPE_NORMAL,
        remind_at=timezone.now() + timedelta(hours=2),
    )
    reminder_b = create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user_b.id,
        staff=owner_b,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=timezone.now() + timedelta(hours=4),
        is_manual=True,
    )

    all_response = auth_client(admin_staff).get("/api/v1/reminders/")
    filtered_response = auth_client(admin_staff).get(f"/api/v1/reminders/?staff_id={owner_b.id}")

    assert all_response.status_code == 200
    assert all_response.data["count"] == 2
    assert filtered_response.status_code == 200
    assert filtered_response.data["count"] == 1
    assert filtered_response.data["results"][0]["id"] == reminder_b.id
    assert filtered_response.data["results"][0]["staff_id"] == owner_b.id


def test_status_and_target_type_filters_apply_to_persisted_reminders(auth_client, create_customer_profile, create_staff):
    owner = create_staff(name="提醒红娘E")
    user = create_customer_profile(owner=owner, phone="13902001005", wechat="persisted_filter_user")
    create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_NORMAL,
        remind_at=timezone.now() + timedelta(hours=2),
        status_value=Reminder.STATUS_PENDING,
    )
    create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=timezone.now() + timedelta(hours=3),
        status_value=Reminder.STATUS_PROCESSED,
    )
    create_reminder(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=owner,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=timezone.now() + timedelta(hours=4),
        status_value=Reminder.STATUS_EXPIRED,
        is_manual=True,
    )

    pending_response = auth_client(owner).get("/api/v1/reminders/?status=pending&target_type=user")
    processed_response = auth_client(owner).get("/api/v1/reminders/?status=processed")
    expired_response = auth_client(owner).get("/api/v1/reminders/?status=expired")

    assert pending_response.status_code == 200
    assert pending_response.data["count"] == 1
    assert pending_response.data["results"][0]["status"] == Reminder.STATUS_PENDING
    assert processed_response.status_code == 200
    assert processed_response.data["count"] == 1
    assert processed_response.data["results"][0]["status"] == Reminder.STATUS_PROCESSED
    assert expired_response.status_code == 200
    assert expired_response.data["count"] == 1
    assert expired_response.data["results"][0]["status"] == Reminder.STATUS_EXPIRED


def test_success_revisit_appears_in_persisted_list(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘F")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_SUCCESS)
    reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=card.id,
        staff=primary_staff,
        remind_type=Reminder.TYPE_SUCCESS_REVISIT,
        remind_at=timezone.now() + timedelta(days=30),
    )

    response = auth_client(primary_staff).get("/api/v1/reminders/?remind_type=success_revisit")

    assert response.status_code == 200
    assert response.data["count"] == 1
    item = response.data["results"][0]
    assert item["id"] == reminder.id
    assert item["target_type"] == Reminder.TARGET_MATCH_CARD
    assert item["target_id"] == card.id
    assert item["remind_type"] == Reminder.TYPE_SUCCESS_REVISIT
    assert item["staff_id"] == primary_staff.id


def test_manual_reminder_create_expires_same_staff_pending_system_reminders_and_refreshes_next_remind_at(
    auth_client,
    create_match_card,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘G")
    female_staff = create_staff(name="女方红娘G")
    card = create_match_card(
        primary_staff=primary_staff,
        male_staff=primary_staff,
        female_staff=female_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )
    own_system_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=card.id,
        staff=primary_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=timezone.now() + timedelta(days=7),
    )
    other_staff_reminder = create_reminder(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=card.id,
        staff=female_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=timezone.now() + timedelta(days=9),
    )

    response = auth_client(primary_staff).post(
        "/api/v1/reminders/manual/",
        {
            "target_type": Reminder.TARGET_MATCH_CARD,
            "target_id": card.id,
            "remind_at": "2026-03-18T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["target_type"] == Reminder.TARGET_MATCH_CARD
    assert response.data["target_id"] == card.id
    assert response.data["remind_type"] == Reminder.TYPE_MANUAL
    assert response.data["status"] == Reminder.STATUS_PENDING
    assert response.data["is_manual"] is True

    own_system_reminder.refresh_from_db()
    other_staff_reminder.refresh_from_db()
    manual_reminder = Reminder.objects.get(id=response.data["id"])
    card.refresh_from_db()
    assert own_system_reminder.status == Reminder.STATUS_EXPIRED
    assert other_staff_reminder.status == Reminder.STATUS_PENDING
    assert manual_reminder.staff_id == primary_staff.id
    assert manual_reminder.is_manual is True
    assert card.next_remind_at == manual_reminder.remind_at


def test_non_owner_cannot_create_manual_user_reminder(auth_client, create_customer_profile, create_staff):
    owner = create_staff(name="用户负责人H")
    other_staff = create_staff(name="无权限红娘H")
    user = create_customer_profile(owner=owner, phone="13902001006", wechat="manual_forbidden_user")

    response = auth_client(other_staff).post(
        "/api/v1/reminders/manual/",
        {
            "target_type": Reminder.TARGET_USER,
            "target_id": user.id,
            "remind_at": "2026-03-18T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


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
