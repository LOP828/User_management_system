import pytest
from uuid import uuid4
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.user.models import CustomerProfile
from apps.reminder.models import Reminder


pytestmark = pytest.mark.django_db


@pytest.fixture
def create_match_card(create_customer_profile, create_staff):
    from apps.matchcard.models import MatchCard

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


def test_create_match_card_sets_users_in_match_and_staff_fields(auth_client, matchmaker_staff, create_customer_profile, create_staff):
    female_staff = create_staff(name="女方红娘")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        name="男方用户A",
        gender=CustomerProfile.GENDER_MALE,
        phone="13900139001",
        wechat="male_a_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        name="女方用户A",
        gender=CustomerProfile.GENDER_FEMALE,
        phone="13900139002",
        wechat="female_a_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )

    response = auth_client(matchmaker_staff).post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": 1,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["male_staff_id"] == matchmaker_staff.id
    assert response.data["female_staff_id"] == female_staff.id
    assert response.data["primary_staff_id"] == matchmaker_staff.id
    male_user.refresh_from_db()
    female_user.refresh_from_db()
    assert male_user.is_in_match is True
    assert female_user.is_in_match is True
    reminders = list(
        Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=response.data["id"],
            status=Reminder.STATUS_PENDING,
        ).order_by("staff_id", "id")
    )
    assert len(reminders) == 2
    assert [reminder.remind_type for reminder in reminders] == [
        Reminder.TYPE_MATCHED_REVISIT,
        Reminder.TYPE_MATCHED_REVISIT,
    ]
    assert {reminder.staff_id for reminder in reminders} == {matchmaker_staff.id, female_staff.id}
    assert all(reminder.is_manual is False for reminder in reminders)


def test_create_match_card_blocks_when_any_user_already_in_match(auth_client, matchmaker_staff, create_customer_profile, create_staff):
    female_staff = create_staff(name="女方红娘B")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        name="男方用户B",
        gender=CustomerProfile.GENDER_MALE,
        phone="13900139003",
        wechat="male_b_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        name="女方用户B",
        gender=CustomerProfile.GENDER_FEMALE,
        phone="13900139004",
        wechat="female_b_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )

    response = auth_client(matchmaker_staff).post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": 1,
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "USER_ALREADY_IN_MATCH"


def test_matchmaker_list_only_returns_involved_cards(auth_client, create_match_card, create_staff):
    viewer = create_staff(name="查看红娘")
    outsider = create_staff(name="无关红娘")
    create_match_card(male_staff=viewer)
    create_match_card(male_staff=outsider, female_staff=outsider, primary_staff=outsider)

    response = auth_client(viewer).get("/api/v1/match-cards/")

    assert response.status_code == 200
    assert response.data["count"] == 1


def test_admin_list_returns_all_cards(auth_client, admin_staff, create_match_card):
    create_match_card()
    create_match_card()

    response = auth_client(admin_staff).get("/api/v1/match-cards/")

    assert response.status_code == 200
    assert response.data["count"] == 2


def test_detail_requires_involved_staff_or_admin(auth_client, create_match_card, create_staff, admin_staff):
    involved_staff = create_staff(name="涉及红娘")
    outsider = create_staff(name="路人红娘")
    card = create_match_card(male_staff=involved_staff, primary_staff=involved_staff)

    involved_response = auth_client(involved_staff).get(f"/api/v1/match-cards/{card.id}/")
    admin_response = auth_client(admin_staff).get(f"/api/v1/match-cards/{card.id}/")
    outsider_response = auth_client(outsider).get(f"/api/v1/match-cards/{card.id}/")

    assert involved_response.status_code == 200
    assert admin_response.status_code == 200
    assert outsider_response.status_code == 403
    assert outsider_response.data["code"] == "PERMISSION_DENIED"


def test_male_staff_can_only_update_male_fields(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘C")
    female_staff = create_staff(name="女方红娘C")
    primary_staff = create_staff(name="主操作红娘C")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)

    ok_response = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "male_feedback": "男方反馈不错",
            "male_heat": 8,
        },
        format="json",
    )
    forbidden_response = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "female_feedback": "越权写女方反馈",
        },
        format="json",
    )

    assert ok_response.status_code == 200
    assert forbidden_response.status_code == 403
    assert forbidden_response.data["code"] == "PERMISSION_DENIED"


def test_female_staff_can_only_update_female_fields(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘D")
    female_staff = create_staff(name="女方红娘D")
    primary_staff = create_staff(name="主操作红娘D")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)

    ok_response = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "female_feedback": "女方反馈不错",
            "female_heat": 7,
        },
        format="json",
    )
    forbidden_response = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "male_feedback": "越权写男方反馈",
        },
        format="json",
    )

    assert ok_response.status_code == 200
    assert forbidden_response.status_code == 403
    assert forbidden_response.data["code"] == "PERMISSION_DENIED"


def test_primary_staff_and_admin_can_update_staff_judgment(auth_client, create_match_card, create_staff, admin_staff):
    male_staff = create_staff(name="男方红娘E")
    female_staff = create_staff(name="女方红娘E")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    primary_response = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "主操作红娘判断关系稳定",
        },
        format="json",
    )
    admin_response = auth_client(admin_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "管理员补充判断",
        },
        format="json",
    )

    assert primary_response.status_code == 200
    assert admin_response.status_code == 200


def test_non_primary_staff_cannot_update_staff_judgment(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘F")
    female_staff = create_staff(name="女方红娘F")
    outsider = create_staff(name="无关红娘F")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    female_response = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "女方尝试越权",
        },
        format="json",
    )
    outsider_response = auth_client(outsider).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "无关人员尝试越权",
        },
        format="json",
    )

    assert female_response.status_code == 403
    assert outsider_response.status_code == 403


def test_match_card_detail_returns_real_followups_and_valid_visit_count(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘详情")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.male_user,
        staff=primary_staff,
        content="男方反馈聊得不错",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.female_user,
        staff=primary_staff,
        content="女方反馈愿意继续",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_MANUAL,
        next_remind_at=timezone.now(),
    )

    response = auth_client(primary_staff).get(f"/api/v1/match-cards/{card.id}/")

    assert response.status_code == 200
    assert response.data["valid_visit_count"] == 2
    assert len(response.data["follow_ups"]) == 2
    assert response.data["follow_ups"][0]["staff_name"] == primary_staff.name
