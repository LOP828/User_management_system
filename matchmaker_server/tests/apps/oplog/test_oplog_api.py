import pytest

from apps.oplog.models import OperationLog
from apps.oplog.services import create_operation_log


pytestmark = pytest.mark.django_db

URL = "/api/v1/operation-logs/"


def _log(operator, action="user_status_changed", target_type="user", target_id=1, **kwargs):
    return create_operation_log(
        operator=operator,
        action=action,
        target_type=target_type,
        target_id=target_id,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------

def test_admin_can_list_logs(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff)
    resp = auth_client(admin_staff).get(URL)
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "results" in data


def test_matchmaker_forbidden(auth_client, matchmaker_staff):
    resp = auth_client(matchmaker_staff).get(URL)
    assert resp.status_code == 403


def test_unauthenticated_forbidden(api_client):
    resp = api_client.get(URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 返回字段
# ---------------------------------------------------------------------------

def test_response_fields(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, before_json={"pool_status": "new_pending"}, after_json={"pool_status": "communicated_pending_recommend"}, reason="测试原因")
    resp = auth_client(admin_staff).get(URL)
    item = resp.json()["results"][0]
    assert "id" in item
    assert "operator_id" in item
    assert "operator_name" in item
    assert "action" in item
    assert "action_display" in item
    assert "target_type" in item
    assert "target_id" in item
    assert "before_json" in item
    assert "after_json" in item
    assert "reason" in item
    assert "created_at" in item


def test_action_display_known_action(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, action="user_status_changed")
    resp = auth_client(admin_staff).get(URL)
    item = resp.json()["results"][0]
    assert item["action_display"] == "用户状态变更"


def test_action_display_unknown_action_falls_back_to_action(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, action="some_future_action")
    resp = auth_client(admin_staff).get(URL)
    item = resp.json()["results"][0]
    assert item["action_display"] == "some_future_action"


# ---------------------------------------------------------------------------
# 过滤
# ---------------------------------------------------------------------------

def test_filter_by_target_type(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, target_type="user")
    _log(matchmaker_staff, target_type="match_card", target_id=99)
    resp = auth_client(admin_staff).get(f"{URL}?target_type=user")
    types = {r["target_type"] for r in resp.json()["results"]}
    assert types == {"user"}


def test_filter_by_target_id(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, target_id=1)
    _log(matchmaker_staff, target_id=2)
    resp = auth_client(admin_staff).get(f"{URL}?target_type=user&target_id=1")
    ids = {r["target_id"] for r in resp.json()["results"]}
    assert ids == {1}


def test_filter_by_operator_id(auth_client, admin_staff, matchmaker_staff, create_staff):
    other = create_staff(name="其他红娘")
    _log(matchmaker_staff)
    _log(other)
    resp = auth_client(admin_staff).get(f"{URL}?operator_id={matchmaker_staff.id}")
    ids = {r["operator_id"] for r in resp.json()["results"]}
    assert ids == {matchmaker_staff.id}


def test_filter_by_action(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, action="user_status_changed")
    _log(matchmaker_staff, action="match_card_created")
    resp = auth_client(admin_staff).get(f"{URL}?action=user_status_changed")
    actions = {r["action"] for r in resp.json()["results"]}
    assert actions == {"user_status_changed"}


# ---------------------------------------------------------------------------
# 分页
# ---------------------------------------------------------------------------

def test_pagination_count_field(auth_client, admin_staff, matchmaker_staff):
    for i in range(3):
        _log(matchmaker_staff, target_id=i + 1)
    resp = auth_client(admin_staff).get(URL)
    data = resp.json()
    assert data["count"] >= 3
    assert "page" in data
    assert "page_size" in data


def test_ordered_by_created_at_desc(auth_client, admin_staff, matchmaker_staff):
    _log(matchmaker_staff, target_id=1)
    _log(matchmaker_staff, target_id=2)
    resp = auth_client(admin_staff).get(URL)
    results = resp.json()["results"]
    assert len(results) >= 2
    # 最新的在前
    assert results[0]["id"] > results[1]["id"]
