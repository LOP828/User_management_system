import pytest
from django.utils import timezone
from rest_framework import status

from apps.matchcard.models import MatchCard
from apps.oplog.models import OperationLog
from apps.user.models import CustomerProfile, UserStatusHistory


pytestmark = pytest.mark.django_db


def test_create_user_requires_minimum_fields(auth_client, matchmaker_staff, create_payment_level):
    client = auth_client(matchmaker_staff)
    payment_level = create_payment_level()

    response = client.post(
        "/api/v1/users/",
        {
            "name": "张三",
            "gender": "male",
            "age": 28,
            "city": "成都",
            "payment_level_id": payment_level.id,
            "owner_id": matchmaker_staff.id,
            "basic_requirement": "希望找25-30岁，成都本地",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "non_field_errors" in response.data["details"]


def test_create_user_overrides_system_fields_and_writes_initial_status_history(
    auth_client,
    matchmaker_staff,
    create_payment_level,
):
    client = auth_client(matchmaker_staff)
    payment_level = create_payment_level()

    response = client.post(
        "/api/v1/users/",
        {
            "name": "张三",
            "gender": "male",
            "age": 28,
            "phone": "13900139000",
            "wechat": "zhangsan_wx",
            "city": "成都",
            "payment_level_id": payment_level.id,
            "owner_id": matchmaker_staff.id,
            "basic_requirement": "希望找25-30岁，成都本地",
            "pool_status": "paused",
            "is_profile_complete": True,
            "is_in_match": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["pool_status"] == CustomerProfile.STATUS_NEW_PENDING
    assert response.data["is_profile_complete"] is False
    assert response.data["is_in_match"] is False
    assert response.data["paid_at"] is None

    user = CustomerProfile.objects.get(id=response.data["id"])
    history = UserStatusHistory.objects.get(user=user)
    assert history.from_status is None
    assert history.to_status == CustomerProfile.STATUS_NEW_PENDING
    assert history.changed_by_id == matchmaker_staff.id


def test_create_user_initializes_last_unmatched_active_at_to_created_at(
    auth_client,
    matchmaker_staff,
    create_payment_level,
):
    client = auth_client(matchmaker_staff)
    payment_level = create_payment_level()

    response = client.post(
        "/api/v1/users/",
        {
            "name": "王五",
            "gender": "male",
            "age": 29,
            "phone": "13900139010",
            "wechat": "wangwu_wx",
            "city": "成都",
            "payment_level_id": payment_level.id,
            "owner_id": matchmaker_staff.id,
            "basic_requirement": "希望找成都本地",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    user = CustomerProfile.objects.get(id=response.data["id"])
    assert user.last_unmatched_active_at == user.created_at


def test_admin_create_user_initializes_last_unmatched_active_at_to_created_at(
    auth_client,
    admin_staff,
    matchmaker_staff,
    create_payment_level,
):
    client = auth_client(admin_staff)
    payment_level = create_payment_level()

    response = client.post(
        "/api/v1/users/",
        {
            "name": "管理员建档用户",
            "gender": "female",
            "age": 27,
            "phone": "13900139013",
            "wechat": "admin_created_user",
            "city": "成都",
            "payment_level_id": payment_level.id,
            "owner_id": matchmaker_staff.id,
            "basic_requirement": "希望找成都本地",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    user = CustomerProfile.objects.get(id=response.data["id"])
    assert user.owner_id == matchmaker_staff.id
    assert user.last_unmatched_active_at == user.created_at


def test_create_user_computes_profile_complete_when_payload_is_complete(
    auth_client,
    matchmaker_staff,
    create_payment_level,
):
    client = auth_client(matchmaker_staff)
    payment_level = create_payment_level()
    profile_detail = {f"field_{i}": f"value_{i}" for i in range(10)}

    response = client.post(
        "/api/v1/users/",
        {
            "name": "李四",
            "gender": "male",
            "age": 30,
            "phone": "13900139011",
            "city": "成都",
            "payment_level_id": payment_level.id,
            "owner_id": matchmaker_staff.id,
            "basic_requirement": "希望找成都本地",
            "profile_detail": profile_detail,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_profile_complete"] is True

    user = CustomerProfile.objects.get(id=response.data["id"])
    assert user.is_profile_complete is True


def test_matchmaker_user_list_only_returns_owned_users(
    auth_client,
    matchmaker_staff,
    create_staff,
    create_customer_profile,
):
    other_staff = create_staff(phone="13800138088", name="其他红娘")
    own_user = create_customer_profile(phone="13900139001")
    create_customer_profile(phone="13900139002", owner=other_staff)

    response = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == own_user.id


def test_admin_user_list_returns_all_users(auth_client, admin_staff, create_customer_profile, create_staff):
    other_staff = create_staff(phone="13800138089", name="其他红娘")
    create_customer_profile(phone="13900139003")
    create_customer_profile(phone="13900139004", owner=other_staff)

    response = auth_client(admin_staff).get("/api/v1/users/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2


def test_owner_and_admin_can_view_user_detail(auth_client, matchmaker_staff, admin_staff, create_customer_profile):
    user = create_customer_profile(phone="13900139005")

    owner_response = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")
    admin_response = auth_client(admin_staff).get(f"/api/v1/users/{user.id}/")

    assert owner_response.status_code == status.HTTP_200_OK
    assert admin_response.status_code == status.HTTP_200_OK
    assert owner_response.data["stats"] == {
        "total_recommendations": 0,
        "total_meetings": 0,
        "total_match_cards": 0,
    }


@pytest.mark.parametrize(
    ("target_gender", "match_stage", "viewer_role"),
    [
        (CustomerProfile.GENDER_MALE, MatchCard.STAGE_INITIAL_CONTACT, "female_staff"),
        (CustomerProfile.GENDER_FEMALE, MatchCard.STAGE_ENDED, "male_staff"),
        (CustomerProfile.GENDER_MALE, MatchCard.STAGE_SUCCESS, "primary_staff"),
    ],
)
def test_related_matchcard_staff_can_view_user_detail_read_only(
    auth_client,
    create_staff,
    create_customer_profile,
    target_gender,
    match_stage,
    viewer_role,
):
    owner = create_staff(phone="13800138094", name="Owner红娘")
    partner_owner = create_staff(phone="13800138095", name="另一侧红娘")
    related_viewer = create_staff(phone="13800138096", name="关联红娘")
    target_user = create_customer_profile(
        phone="13900139011",
        owner=owner,
        gender=target_gender,
        is_in_match=match_stage in {
            MatchCard.STAGE_INITIAL_CONTACT,
            MatchCard.STAGE_STABLE_CONTACT,
            MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
        },
    )
    partner_user = create_customer_profile(
        phone="13900139012",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE if target_gender == CustomerProfile.GENDER_MALE else CustomerProfile.GENDER_MALE,
        is_in_match=target_user.is_in_match,
    )
    if target_gender == CustomerProfile.GENDER_MALE:
        male_user = target_user
        female_user = partner_user
        male_staff = owner
        female_staff = related_viewer if viewer_role == "female_staff" else partner_owner
    else:
        male_user = partner_user
        female_user = target_user
        male_staff = related_viewer if viewer_role == "male_staff" else partner_owner
        female_staff = owner

    MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_staff,
        female_staff=female_staff,
        primary_staff=related_viewer if viewer_role == "primary_staff" else owner,
        stage=match_stage,
    )

    response = auth_client(related_viewer).get(f"/api/v1/users/{target_user.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == target_user.id


def test_non_owner_matchmaker_cannot_view_user_detail(auth_client, create_staff, create_customer_profile):
    owner = create_staff(phone="13800138090", name="A红娘")
    outsider = create_staff(phone="13800138091", name="B红娘")
    user = create_customer_profile(phone="13900139006", owner=owner)

    response = auth_client(outsider).get(f"/api/v1/users/{user.id}/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_patch_user_recalculates_profile_complete(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(
        phone="13900139007",
        profile_detail=None,
        is_profile_complete=False,
    )
    profile_detail = {f"field_{i}": f"value_{i}" for i in range(10)}

    response = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"profile_detail": profile_detail},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.is_profile_complete is True


def test_patch_user_can_write_paid_at(auth_client, matchmaker_staff, create_customer_profile):
    user = create_customer_profile(phone="13900139008", paid_at=None)

    response = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"paid_at": "2026-03-14T09:30:00+08:00"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.paid_at is not None


def test_patch_user_cannot_modify_system_managed_tags_or_emotional_history(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
):
    user = create_customer_profile(
        phone="13900139010",
        tags=["待重新推荐"],
        emotional_history=[{"match_card_id": 1, "partner_name": "王**"}],
    )

    response = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {
            "tags": ["已手动篡改"],
            "emotional_history": [{"match_card_id": 99, "partner_name": "李**"}],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.tags == ["待重新推荐"]
    assert user.emotional_history == [{"match_card_id": 1, "partner_name": "王**"}]


def test_non_owner_matchmaker_cannot_patch_user(auth_client, create_staff, create_customer_profile):
    owner = create_staff(phone="13800138092", name="A红娘")
    outsider = create_staff(phone="13800138093", name="B红娘")
    user = create_customer_profile(phone="13900139009", owner=owner)

    response = auth_client(outsider).patch(
        f"/api/v1/users/{user.id}/",
        {"city": "上海"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_related_matchcard_staff_cannot_patch_user_detail(
    auth_client,
    create_staff,
    create_customer_profile,
):
    owner = create_staff(phone="13800138097", name="Owner红娘2")
    related_viewer = create_staff(phone="13800138098", name="关联红娘2")
    partner_owner = create_staff(phone="13800138099", name="另一侧红娘2")
    target_user = create_customer_profile(
        phone="13900139013",
        owner=owner,
        gender=CustomerProfile.GENDER_MALE,
        is_in_match=True,
    )
    partner_user = create_customer_profile(
        phone="13900139014",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    MatchCard.objects.create(
        male_user=target_user,
        female_user=partner_user,
        male_staff=owner,
        female_staff=related_viewer,
        primary_staff=owner,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )

    response = auth_client(related_viewer).patch(
        f"/api/v1/users/{target_user.id}/",
        {"city": "上海"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"
    target_user.refresh_from_db()
    assert target_user.city == "成都"


# ── A3: admin owner_id change tests ─────────────────────────────────────


def test_admin_can_change_owner_id_with_force(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
):
    old_owner = create_staff(phone="13800138200", name="旧红娘")
    new_owner = create_staff(phone="13800138201", name="新红娘")
    primary_staff = create_staff(phone="13800138207", name="主操作红娘")
    female_owner = create_staff(phone="13800138208", name="女方红娘")
    other_female_owner = create_staff(phone="13800138209", name="女方红娘2")
    user = create_customer_profile(phone="13900139200", owner=old_owner, is_in_match=True)
    female_user = create_customer_profile(
        phone="13900139204",
        owner=female_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    other_female_user = create_customer_profile(
        phone="13900139205",
        owner=other_female_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    active_card = MatchCard.objects.create(
        male_user=user,
        female_user=female_user,
        male_staff=old_owner,
        female_staff=female_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
    )
    pending_review_card = MatchCard.objects.create(
        male_user=user,
        female_user=other_female_user,
        male_staff=old_owner,
        female_staff=other_female_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
    )
    ended_card = MatchCard.objects.create(
        male_user=user,
        female_user=create_customer_profile(
            phone="13900139206",
            owner=female_owner,
            gender=CustomerProfile.GENDER_FEMALE,
            is_in_match=False,
        ),
        male_staff=old_owner,
        female_staff=female_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_ENDED,
    )

    before_change = timezone.now()
    assert auth_client(old_owner).get("/api/v1/reminders/").data["count"] == 2

    response = auth_client(admin_staff).patch(
        f"/api/v1/users/{user.id}/",
        {
            "owner_id": new_owner.id,
            "force": True,
            "force_reason": "管理员调整负责人",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    active_card.refresh_from_db()
    pending_review_card.refresh_from_db()
    ended_card.refresh_from_db()
    assert user.owner_id == new_owner.id
    assert user.last_action_at is not None
    assert user.last_action_at >= before_change
    assert active_card.male_staff_id == new_owner.id
    assert pending_review_card.male_staff_id == new_owner.id
    assert ended_card.male_staff_id == old_owner.id
    assert active_card.female_staff_id == female_owner.id
    assert active_card.primary_staff_id == primary_staff.id
    assert auth_client(old_owner).get("/api/v1/reminders/").data["count"] == 0
    new_owner_reminders = auth_client(new_owner).get("/api/v1/reminders/")
    assert new_owner_reminders.data["count"] == 2
    assert all(item["staff_id"] == new_owner.id for item in new_owner_reminders.data["results"])

    oplog = OperationLog.objects.filter(target_type="user", target_id=user.id).latest("id")
    assert oplog.action == "admin_force_change"
    assert oplog.before_json["owner_id"] == old_owner.id
    assert oplog.after_json["owner_id"] == new_owner.id
    assert oplog.reason == "管理员调整负责人"


def test_admin_change_owner_id_requires_force(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
):
    old_owner = create_staff(phone="13800138202", name="旧红娘2")
    new_owner = create_staff(phone="13800138203", name="新红娘2")
    user = create_customer_profile(phone="13900139201", owner=old_owner)

    response = auth_client(admin_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"owner_id": new_owner.id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "FORCE_REASON_REQUIRED"
    user.refresh_from_db()
    assert user.owner_id == old_owner.id


def test_admin_change_owner_id_requires_force_reason(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
):
    old_owner = create_staff(phone="13800138204", name="旧红娘3")
    new_owner = create_staff(phone="13800138205", name="新红娘3")
    user = create_customer_profile(phone="13900139202", owner=old_owner)

    response = auth_client(admin_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"owner_id": new_owner.id, "force": True},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "FORCE_REASON_REQUIRED"


def test_admin_change_owner_id_updates_active_female_side_match_cards_only(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
):
    old_owner = create_staff(phone="13800138210", name="旧女方红娘")
    new_owner = create_staff(phone="13800138211", name="新女方红娘")
    male_owner = create_staff(phone="13800138212", name="男方红娘")
    primary_staff = create_staff(phone="13800138213", name="主操作红娘2")
    female_user = create_customer_profile(
        phone="13900139207",
        owner=old_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    male_user = create_customer_profile(
        phone="13900139208",
        owner=male_owner,
        gender=CustomerProfile.GENDER_MALE,
        is_in_match=True,
    )
    active_card = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_owner,
        female_staff=old_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )
    success_card = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_owner,
        female_staff=old_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_SUCCESS,
    )

    response = auth_client(admin_staff).patch(
        f"/api/v1/users/{female_user.id}/",
        {
            "owner_id": new_owner.id,
            "force": True,
            "force_reason": "管理员调整女方负责人",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    female_user.refresh_from_db()
    active_card.refresh_from_db()
    success_card.refresh_from_db()
    assert female_user.owner_id == new_owner.id
    assert active_card.female_staff_id == new_owner.id
    assert active_card.male_staff_id == male_owner.id
    assert active_card.primary_staff_id == primary_staff.id
    assert success_card.female_staff_id == old_owner.id


def test_admin_change_owner_id_does_not_touch_unrelated_active_cards_or_users(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
):
    old_owner = create_staff(phone="13800138214", name="旧红娘4")
    new_owner = create_staff(phone="13800138215", name="新红娘4")
    target_partner_owner = create_staff(phone="13800138216", name="目标女方红娘")
    unrelated_partner_owner = create_staff(phone="13800138217", name="无关女方红娘")
    primary_staff = create_staff(phone="13800138218", name="主操作红娘3")

    target_user = create_customer_profile(phone="13900139209", owner=old_owner, is_in_match=True)
    target_partner = create_customer_profile(
        phone="13900139210",
        owner=target_partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    unrelated_user = create_customer_profile(phone="13900139211", owner=old_owner, is_in_match=True)
    unrelated_partner = create_customer_profile(
        phone="13900139212",
        owner=unrelated_partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )

    target_card = MatchCard.objects.create(
        male_user=target_user,
        female_user=target_partner,
        male_staff=old_owner,
        female_staff=target_partner_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
    )
    unrelated_card = MatchCard.objects.create(
        male_user=unrelated_user,
        female_user=unrelated_partner,
        male_staff=old_owner,
        female_staff=unrelated_partner_owner,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )

    response = auth_client(admin_staff).patch(
        f"/api/v1/users/{target_user.id}/",
        {
            "owner_id": new_owner.id,
            "force": True,
            "force_reason": "只调整目标用户负责人",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    target_user.refresh_from_db()
    target_card.refresh_from_db()
    unrelated_user.refresh_from_db()
    unrelated_card.refresh_from_db()
    assert target_user.owner_id == new_owner.id
    assert target_card.male_staff_id == new_owner.id
    assert unrelated_user.owner_id == old_owner.id
    assert unrelated_card.male_staff_id == old_owner.id
    assert unrelated_card.female_staff_id == unrelated_partner_owner.id
    assert unrelated_card.primary_staff_id == primary_staff.id


def test_matchmaker_cannot_change_owner_id(
    auth_client,
    matchmaker_staff,
    create_staff,
    create_customer_profile,
):
    new_owner = create_staff(phone="13800138206", name="另一红娘")
    user = create_customer_profile(phone="13900139203")

    response = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {
            "owner_id": new_owner.id,
            "force": True,
            "force_reason": "试图改负责人",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    user.refresh_from_db()
    assert user.owner_id == matchmaker_staff.id
