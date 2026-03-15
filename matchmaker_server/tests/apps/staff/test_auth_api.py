import pytest
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
def test_login_returns_token_pair_and_staff_payload(api_client, matchmaker_staff):
    response = api_client.post(
        "/api/v1/auth/login/",
        {
            "phone": matchmaker_staff.phone,
            "password": "Passw0rd123!",
        },
        format="json",
    )

    assert response.status_code == 200
    assert "access_token" in response.data
    assert "refresh_token" in response.data
    assert response.data["staff"] == {
        "id": matchmaker_staff.id,
        "name": matchmaker_staff.name,
        "role": matchmaker_staff.role,
        "phone": matchmaker_staff.phone,
    }


@pytest.mark.django_db
def test_refresh_returns_new_access_token(api_client, matchmaker_staff):
    refresh = RefreshToken.for_user(matchmaker_staff)

    response = api_client.post(
        "/api/v1/auth/refresh/",
        {"refresh_token": str(refresh)},
        format="json",
    )

    assert response.status_code == 200
    assert "access_token" in response.data


@pytest.mark.django_db
def test_wechat_login_returns_placeholder_response(api_client):
    response = api_client.post("/api/v1/auth/wechat-login/", {"code": "wx-code"}, format="json")

    assert response.status_code == 501
    assert response.data["code"] == "NOT_IMPLEMENTED"


@pytest.mark.django_db
def test_protected_endpoint_without_token_returns_401(api_client):
    response = api_client.get("/api/v1/staff/me/")

    assert response.status_code == 401
    assert response.data["code"] == "AUTH_TOKEN_INVALID"
