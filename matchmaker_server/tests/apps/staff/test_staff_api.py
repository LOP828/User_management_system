import pytest
from django.utils import timezone

from apps.staff.models import Staff


@pytest.mark.django_db
def test_staff_me_returns_current_staff(auth_client, matchmaker_staff):
    response = auth_client(matchmaker_staff).get("/api/v1/staff/me/")

    assert response.status_code == 200
    assert response.data == {
        "id": matchmaker_staff.id,
        "name": matchmaker_staff.name,
        "role": matchmaker_staff.role,
        "phone": matchmaker_staff.phone,
        "wechat_id": matchmaker_staff.wechat_id,
        "status": matchmaker_staff.status,
    }


@pytest.mark.django_db
def test_staff_list_returns_lite_fields_for_matchmaker(auth_client, matchmaker_staff, admin_staff):
    response = auth_client(matchmaker_staff).get("/api/v1/staff/")

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["page"] == 1
    assert response.data["page_size"] == 20
    assert set(response.data["results"][0].keys()) == {"id", "name", "role", "status"}


@pytest.mark.django_db
def test_staff_list_returns_full_fields_for_admin(auth_client, matchmaker_staff, admin_staff):
    response = auth_client(admin_staff).get("/api/v1/staff/")

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert set(response.data["results"][0].keys()) == {"id", "name", "role", "phone", "wechat_id", "status"}


@pytest.mark.django_db
def test_staff_list_supports_role_and_status_filters(auth_client, admin_staff, create_staff):
    create_staff(phone="13800138009", name="停用红娘", status=Staff.STATUS_DISABLED)

    response = auth_client(admin_staff).get("/api/v1/staff/?role=matchmaker&status=disabled")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["status"] == Staff.STATUS_DISABLED


@pytest.mark.django_db
def test_admin_can_create_staff_and_password_is_hashed(auth_client, admin_staff):
    response = auth_client(admin_staff).post(
        "/api/v1/staff/",
        {
            "name": "新红娘",
            "phone": "13800138111",
            "role": Staff.ROLE_MATCHMAKER,
            "status": Staff.STATUS_ACTIVE,
            "wechat_id": "wx_new",
            "password": "Passw0rd123!",
        },
        format="json",
    )

    assert response.status_code == 201
    created_staff = Staff.objects.get(phone="13800138111")
    assert created_staff.password != "Passw0rd123!"
    assert created_staff.check_password("Passw0rd123!")
    assert response.data["phone"] == "13800138111"


@pytest.mark.django_db
def test_matchmaker_cannot_create_staff(auth_client, matchmaker_staff):
    response = auth_client(matchmaker_staff).post(
        "/api/v1/staff/",
        {
            "name": "新红娘",
            "phone": "13800138112",
            "role": Staff.ROLE_MATCHMAKER,
            "status": Staff.STATUS_ACTIVE,
            "password": "Passw0rd123!",
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_admin_cannot_reuse_phone_from_soft_deleted_staff(auth_client, admin_staff, create_staff):
    retired_staff = create_staff(phone="13800138113", name="已删除红娘")
    retired_staff.deleted_at = timezone.now()
    retired_staff.save(update_fields=["deleted_at", "updated_at"])

    response = auth_client(admin_staff).post(
        "/api/v1/staff/",
        {
            "name": "新红娘",
            "phone": retired_staff.phone,
            "role": Staff.ROLE_MATCHMAKER,
            "status": Staff.STATUS_ACTIVE,
            "password": "Passw0rd123!",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "phone" in response.data["details"]


@pytest.mark.django_db
def test_admin_can_patch_staff_and_reset_password(auth_client, admin_staff, matchmaker_staff):
    response = auth_client(admin_staff).patch(
        f"/api/v1/staff/{matchmaker_staff.id}/",
        {
            "name": "红娘A-已更新",
            "password": "Passw0rd456!",
        },
        format="json",
    )

    assert response.status_code == 200
    matchmaker_staff.refresh_from_db()
    assert matchmaker_staff.name == "红娘A-已更新"
    assert matchmaker_staff.check_password("Passw0rd456!")
