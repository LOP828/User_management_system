import pytest
from uuid import uuid4

from apps.matchcard.models import MatchCard
from apps.transfer.models import UserTransferRequest
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pending_req(user, from_staff, to_staff):
    return UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason="测试原因",
        status=UserTransferRequest.STATUS_PENDING,
    )


def _make_user(create_customer_profile, owner, **kwargs):
    suffix = f"{uuid4().int % 10**8:08d}"
    return create_customer_profile(
        owner=owner,
        phone=f"138{suffix}",
        wechat=f"wx_{suffix}",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/transfer-requests/ — 发起转移申请
# ---------------------------------------------------------------------------

def test_create_transfer_request_success(auth_client, matchmaker_staff, create_customer_profile, create_staff):
    to_staff = create_staff(name="目标红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)

    client = auth_client(matchmaker_staff)
    resp = client.post(
        "/api/v1/transfer-requests/",
        data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "本人即将休假"},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == UserTransferRequest.STATUS_PENDING
    assert data["from_staff_id"] == matchmaker_staff.id
    assert data["to_staff_id"] == to_staff.id
    assert data["user_id"] == user.id


def test_create_transfer_request_matchmaker_cannot_transfer_others_user(
    auth_client, create_staff, create_customer_profile
):
    owner = create_staff(name="原始红娘")
    other = create_staff(name="发起者红娘")
    to_staff = create_staff(name="目标红娘")
    user = _make_user(create_customer_profile, owner)

    client = auth_client(other)
    resp = client.post(
        "/api/v1/transfer-requests/",
        data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "想抢人"},
        format="json",
    )
    assert resp.status_code == 403


def test_create_transfer_request_br_001_same_staff(
    auth_client, matchmaker_staff, create_customer_profile
):
    user = _make_user(create_customer_profile, matchmaker_staff)

    client = auth_client(matchmaker_staff)
    resp = client.post(
        "/api/v1/transfer-requests/",
        data={"user_id": user.id, "to_staff_id": matchmaker_staff.id, "reason": "转给自己"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "TRANSFER_SAME_STAFF"


def test_create_transfer_request_br_001_pending_exists(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="目标红娘A")
    to_staff2 = create_staff(name="目标红娘B")
    user = _make_user(create_customer_profile, matchmaker_staff)
    _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(matchmaker_staff)
    resp = client.post(
        "/api/v1/transfer-requests/",
        data={"user_id": user.id, "to_staff_id": to_staff2.id, "reason": "重复申请"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "TRANSFER_PENDING_EXISTS"


def test_create_transfer_request_br_001_invalid_to_staff(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """目标红娘为 disabled 时应返回 TO_STAFF_INVALID。"""
    from apps.staff.models import Staff
    to_staff = create_staff(name="已停用红娘", status=Staff.STATUS_DISABLED)
    user = _make_user(create_customer_profile, matchmaker_staff)

    client = auth_client(matchmaker_staff)
    resp = client.post(
        "/api/v1/transfer-requests/",
        data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "目标无效"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "TO_STAFF_INVALID"


def test_admin_can_create_transfer_for_any_user(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="目标红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)

    client = auth_client(admin_staff)
    resp = client.post(
        "/api/v1/transfer-requests/",
        data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "admin 强制转移"},
        format="json",
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /api/v1/transfer-requests/{id}/approve/ — 审批通过
# ---------------------------------------------------------------------------

def test_approve_transfer_request_success(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(admin_staff)
    resp = client.post(f"/api/v1/transfer-requests/{req.id}/approve/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == UserTransferRequest.STATUS_APPROVED
    assert data["message"] == "转移已生效"

    req.refresh_from_db()
    assert req.status == UserTransferRequest.STATUS_APPROVED
    assert req.reviewer_id == admin_staff.id


def test_approve_transfer_request_updates_user_owner(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(admin_staff)
    client.post(f"/api/v1/transfer-requests/{req.id}/approve/")

    user.refresh_from_db()
    assert user.owner_id == to_staff.id
    assert user.last_action_at is not None


def test_approve_transfer_request_syncs_match_card_staff(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    """审批通过后，进行中配对卡的 male_staff_id 应同步为新负责人。"""
    to_staff = create_staff(name="接收红娘")
    suffix = f"{uuid4().int % 10**8:08d}"
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        gender=CustomerProfile.GENDER_MALE,
        phone=f"139{suffix}",
        wechat=f"male_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    female_staff = create_staff(name="女方红娘")
    suffix2 = f"{uuid4().int % 10**8:08d}"
    female_user = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        phone=f"137{suffix2}",
        wechat=f"female_{suffix2}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    mc = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=matchmaker_staff,
        female_staff=female_staff,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
        risk_level=MatchCard.RISK_NONE,
    )

    req = _pending_req(male_user, matchmaker_staff, to_staff)
    client = auth_client(admin_staff)
    resp = client.post(f"/api/v1/transfer-requests/{req.id}/approve/")
    assert resp.status_code == 200
    affected = resp.json()["affected_match_cards"]
    assert any(a["id"] == mc.id and a["updated_field"] == "male_staff_id" for a in affected)

    mc.refresh_from_db()
    assert mc.male_staff_id == to_staff.id


def test_approve_transfer_request_only_admin(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/transfer-requests/{req.id}/approve/")
    assert resp.status_code == 403


def test_approve_transfer_request_not_pending(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    """已审批的申请不能重复审批。"""
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)
    req.status = UserTransferRequest.STATUS_APPROVED
    req.save(update_fields=["status"])

    client = auth_client(admin_staff)
    resp = client.post(f"/api/v1/transfer-requests/{req.id}/approve/")
    assert resp.status_code == 400
    assert resp.json()["code"] == "TRANSFER_NOT_PENDING"


# ---------------------------------------------------------------------------
# POST /api/v1/transfer-requests/{id}/reject/ — 驳回
# ---------------------------------------------------------------------------

def test_reject_transfer_request_success(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(admin_staff)
    resp = client.post(
        f"/api/v1/transfer-requests/{req.id}/reject/",
        data={"review_note": "当前用户较少，建议不转移"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == UserTransferRequest.STATUS_REJECTED
    assert data["review_note"] == "当前用户较少，建议不转移"

    req.refresh_from_db()
    assert req.status == UserTransferRequest.STATUS_REJECTED
    assert req.reviewer_id == admin_staff.id


def test_reject_transfer_request_user_owner_unchanged(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    """驳回后 user.owner_id 不能变更。"""
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(admin_staff)
    client.post(f"/api/v1/transfer-requests/{req.id}/reject/", data={}, format="json")

    user.refresh_from_db()
    assert user.owner_id == matchmaker_staff.id


def test_reject_transfer_request_only_admin(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/transfer-requests/{req.id}/reject/", data={}, format="json")
    assert resp.status_code == 403


def test_reject_transfer_request_not_pending(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)
    req.status = UserTransferRequest.STATUS_REJECTED
    req.save(update_fields=["status"])

    client = auth_client(admin_staff)
    resp = client.post(f"/api/v1/transfer-requests/{req.id}/reject/", data={}, format="json")
    assert resp.status_code == 400
    assert resp.json()["code"] == "TRANSFER_NOT_PENDING"


# ---------------------------------------------------------------------------
# GET /api/v1/transfer-requests/ — 列表
# ---------------------------------------------------------------------------

def test_list_transfer_requests_admin_sees_all(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘A")
    other_staff = create_staff(name="其他红娘")
    to_staff2 = create_staff(name="接收红娘B")

    user1 = _make_user(create_customer_profile, matchmaker_staff)
    user2 = _make_user(create_customer_profile, other_staff)
    req1 = _pending_req(user1, matchmaker_staff, to_staff)
    req2 = _pending_req(user2, other_staff, to_staff2)

    client = auth_client(admin_staff)
    resp = client.get("/api/v1/transfer-requests/")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert req1.id in ids
    assert req2.id in ids


def test_list_transfer_requests_matchmaker_sees_own(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘A")
    other_staff = create_staff(name="其他红娘")
    to_staff2 = create_staff(name="接收红娘B")

    user1 = _make_user(create_customer_profile, matchmaker_staff)
    user2 = _make_user(create_customer_profile, other_staff)
    req1 = _pending_req(user1, matchmaker_staff, to_staff)
    req2 = _pending_req(user2, other_staff, to_staff2)

    client = auth_client(matchmaker_staff)
    resp = client.get("/api/v1/transfer-requests/")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert req1.id in ids
    assert req2.id not in ids


def test_list_transfer_requests_status_filter(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _make_user(create_customer_profile, matchmaker_staff)
    req = _pending_req(user, matchmaker_staff, to_staff)
    req.status = UserTransferRequest.STATUS_APPROVED
    req.save(update_fields=["status"])

    user2 = _make_user(create_customer_profile, matchmaker_staff)
    pending_req = _pending_req(user2, matchmaker_staff, to_staff)

    client = auth_client(admin_staff)
    resp = client.get("/api/v1/transfer-requests/?status=pending")
    ids = [r["id"] for r in resp.json()]
    assert pending_req.id in ids
    assert req.id not in ids
