import pytest

from apps.config_mgmt.models import ReasonEnum


@pytest.mark.django_db
def test_reason_enum_list_supports_category_and_active_filters(auth_client, matchmaker_staff, create_reason_enum):
    create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="暂停原因", sort_order=1, is_active=True)
    create_reason_enum(category=ReasonEnum.CATEGORY_RISK, label="风险原因", sort_order=2, is_active=False)

    response = auth_client(matchmaker_staff).get("/api/v1/reason-enums/?category=pause&is_active=true")

    assert response.status_code == 200
    assert response.data["count"] >= 1
    assert all(item["category"] == "pause" for item in response.data["results"])
    assert all(item["is_active"] is True for item in response.data["results"])


@pytest.mark.django_db
def test_admin_can_create_and_patch_reason_enum(auth_client, admin_staff):
    create_response = auth_client(admin_staff).post(
        "/api/v1/reason-enums/",
        {
            "category": ReasonEnum.CATEGORY_MATCH_END,
            "label": "双方家庭不同意",
            "sort_order": 5,
            "is_active": True,
        },
        format="json",
    )

    assert create_response.status_code == 201
    reason_id = create_response.data["id"]

    patch_response = auth_client(admin_staff).patch(
        f"/api/v1/reason-enums/{reason_id}/",
        {"label": "双方家庭反对", "is_active": False},
        format="json",
    )

    assert patch_response.status_code == 200
    reason = ReasonEnum.objects.get(pk=reason_id)
    assert reason.label == "双方家庭反对"
    assert reason.is_active is False


@pytest.mark.django_db
def test_matchmaker_cannot_create_or_patch_reason_enum(auth_client, matchmaker_staff, create_reason_enum):
    reason = create_reason_enum()

    create_response = auth_client(matchmaker_staff).post(
        "/api/v1/reason-enums/",
        {
            "category": ReasonEnum.CATEGORY_TRANSFER,
            "label": "用户要求换红娘",
            "sort_order": 1,
        },
        format="json",
    )
    patch_response = auth_client(matchmaker_staff).patch(
        f"/api/v1/reason-enums/{reason.id}/",
        {"label": "新标签"},
        format="json",
    )

    assert create_response.status_code == 403
    assert patch_response.status_code == 403
