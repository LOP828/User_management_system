import pytest

from apps.config_mgmt.models import PaymentLevel


@pytest.mark.django_db
def test_payment_level_list_returns_expected_fields(auth_client, matchmaker_staff, create_payment_level):
    create_payment_level()

    response = auth_client(matchmaker_staff).get("/api/v1/payment-levels/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert set(response.data["results"][0].keys()) == {
        "id",
        "name",
        "sort_order",
        "is_active",
        "homepage_weight",
        "recommend_limit",
        "pause_revisit_days",
        "followup_timeout_days",
        "note",
    }


@pytest.mark.django_db
def test_admin_can_create_and_patch_payment_level(auth_client, admin_staff):
    create_response = auth_client(admin_staff).post(
        "/api/v1/payment-levels/",
        {
            "name": "高级会员",
            "sort_order": 2,
            "is_active": True,
            "homepage_weight": 20,
            "recommend_limit": 5,
            "pause_revisit_days": 14,
            "followup_timeout_days": 5,
            "note": "高权重",
        },
        format="json",
    )

    assert create_response.status_code == 201
    level_id = create_response.data["id"]

    patch_response = auth_client(admin_staff).patch(
        f"/api/v1/payment-levels/{level_id}/",
        {"recommend_limit": 6, "note": "已更新"},
        format="json",
    )

    assert patch_response.status_code == 200
    level = PaymentLevel.objects.get(pk=level_id)
    assert level.recommend_limit == 6
    assert level.note == "已更新"


@pytest.mark.django_db
def test_matchmaker_cannot_create_or_patch_payment_level(auth_client, matchmaker_staff, create_payment_level):
    level = create_payment_level()

    create_response = auth_client(matchmaker_staff).post(
        "/api/v1/payment-levels/",
        {
            "name": "禁止创建",
            "sort_order": 9,
            "is_active": True,
            "homepage_weight": 1,
            "recommend_limit": 1,
            "pause_revisit_days": 30,
            "followup_timeout_days": 7,
            "note": "",
        },
        format="json",
    )
    patch_response = auth_client(matchmaker_staff).patch(
        f"/api/v1/payment-levels/{level.id}/",
        {"name": "禁止修改"},
        format="json",
    )

    assert create_response.status_code == 403
    assert patch_response.status_code == 403
