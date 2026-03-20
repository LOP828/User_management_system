import os

from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.config_mgmt.models import PaymentLevel
from apps.staff.models import Staff
from apps.user.models import CustomerProfile


def _auth_client(staff):
    refresh = RefreshToken.for_user(staff)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def test_seed_minimal_integration_data_command_is_idempotent_and_api_ready(db, capsys):
    call_command("seed_minimal_integration_data")
    call_command("seed_minimal_integration_data")

    admin = Staff.objects.get(phone="13800000000")
    owner = Staff.objects.get(phone="13800000001")
    users = list(CustomerProfile.objects.filter(phone__in=["13990000001", "13990000002", "13990000003"]).order_by("phone"))
    payment_levels = PaymentLevel.objects.filter(name__in=["联调基础档", "联调中级档", "联调超时档"])
    admin_password = os.environ.get("INIT_ADMIN_PASSWORD", "Passw0rd123!")

    assert admin.role == Staff.ROLE_ADMIN
    assert admin.check_password(admin_password)
    assert owner.role == Staff.ROLE_MATCHMAKER
    assert owner.check_password("Passw0rd123!")
    assert payment_levels.count() == 3
    assert len(users) == 3

    client = _auth_client(admin)

    list_resp = client.get("/api/v1/users/")
    assert list_resp.status_code == 200
    assert list_resp.data["count"] >= 3
    list_ids = [item["id"] for item in list_resp.data["results"]]
    assert set(user.id for user in users).issubset(set(list_ids))

    verify_id = users[0].id
    detail_resp = client.get(f"/api/v1/users/{verify_id}/")
    assert detail_resp.status_code == 200
    assert detail_resp.data["id"] == verify_id

    asc_resp = client.get("/api/v1/users/?ordering=priority_score")
    desc_resp = client.get("/api/v1/users/?ordering=-priority_score")
    assert asc_resp.status_code == 200
    assert desc_resp.status_code == 200

    asc_seed = [(item["id"], item["priority_score"]) for item in asc_resp.data["results"] if item["id"] in set(user.id for user in users)]
    desc_seed = [(item["id"], item["priority_score"]) for item in desc_resp.data["results"] if item["id"] in set(user.id for user in users)]

    assert asc_seed == sorted(asc_seed, key=lambda item: item[1])
    assert desc_seed == sorted(desc_seed, key=lambda item: item[1], reverse=True)
    assert [item[0] for item in asc_seed] == [item[0] for item in reversed(desc_seed)]

    print(f"verify_user_id={verify_id}")
    print(f"list_summary={[{'id': item['id'], 'priority_score': item['priority_score']} for item in list_resp.data['results'] if item['id'] in set(user.id for user in users)]}")
    print(f"asc_summary={asc_seed}")
    print(f"desc_summary={desc_seed}")

    captured = capsys.readouterr()
    assert "verify_user_id=" in captured.out
