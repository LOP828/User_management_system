import pytest
from uuid import uuid4

from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db

URL = "/api/v1/search/"


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _user(create_customer_profile, owner, name="张三", **kw):
    suffix = f"{uuid4().int % 10**8:08d}"
    return create_customer_profile(
        owner=owner,
        name=name,
        phone=f"138{suffix}",
        wechat=f"wx_{suffix}",
        **kw,
    )


def _match_card(male_user, female_user, male_staff, female_staff, stage=MatchCard.STAGE_INITIAL_CONTACT):
    return MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_staff,
        female_staff=female_staff,
        primary_staff=male_staff,
        stage=stage,
        risk_level=MatchCard.RISK_NONE,
    )


def _make_mc_pair(create_customer_profile, male_staff, female_staff):
    s1 = f"{uuid4().int % 10**8:08d}"
    s2 = f"{uuid4().int % 10**8:08d}"
    male = create_customer_profile(
        owner=male_staff,
        gender=CustomerProfile.GENDER_MALE,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
        phone=f"139{s1}",
        wechat=f"male_{s1}",
    )
    female = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
        phone=f"137{s2}",
        wechat=f"female_{s2}",
    )
    return male, female


# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------

def test_unauthenticated_forbidden(api_client):
    resp = api_client.get(URL)
    assert resp.status_code == 401


def test_matchmaker_can_search(auth_client, matchmaker_staff):
    resp = auth_client(matchmaker_staff).get(URL)
    assert resp.status_code == 200


def test_admin_can_search(auth_client, admin_staff):
    resp = auth_client(admin_staff).get(URL)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 响应结构
# ---------------------------------------------------------------------------

def test_response_structure(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    _user(create_customer_profile, matchmaker_staff)
    resp = auth_client(admin_staff).get(f"{URL}?q=张三")
    data = resp.json()
    assert "count" in data
    assert "results" in data
    assert "page" in data
    assert "page_size" in data


def test_result_fields(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    _user(create_customer_profile, matchmaker_staff, name="字段测试用户")
    resp = auth_client(admin_staff).get(f"{URL}?q=字段测试用户")
    item = resp.json()["results"][0]
    assert "id" in item
    assert "name" in item
    assert "gender" in item
    assert "age" in item
    assert "pool_status" in item
    assert "pool_status_display" in item
    assert "is_in_match" in item
    assert "owner_id" in item
    assert "owner_name" in item
    assert "last_action_at" in item
    assert "active_match_card_id" in item
    assert "match_field" in item


# ---------------------------------------------------------------------------
# 关键词搜索
# ---------------------------------------------------------------------------

def test_search_by_name(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    u = _user(create_customer_profile, matchmaker_staff, name="李梅梅")
    _user(create_customer_profile, matchmaker_staff, name="王大力")
    resp = auth_client(admin_staff).get(f"{URL}?q=梅梅")
    ids = [r["id"] for r in resp.json()["results"]]
    assert u.id in ids
    assert all(r["name"] == "李梅梅" for r in resp.json()["results"] if r["id"] == u.id)


def test_search_by_phone(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    suffix = f"{uuid4().int % 10**8:08d}"
    u = create_customer_profile(
        owner=matchmaker_staff,
        name="手机搜索用户",
        phone=f"139{suffix}",
        wechat=f"wx_phone_{suffix}",
    )
    resp = auth_client(admin_staff).get(f"{URL}?q={u.phone}")
    ids = [r["id"] for r in resp.json()["results"]]
    assert u.id in ids


def test_search_by_wechat(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    suffix = f"{uuid4().int % 10**8:08d}"
    u = create_customer_profile(
        owner=matchmaker_staff,
        name="微信搜索用户",
        phone=f"138{suffix}",
        wechat=f"uniquewechat_{suffix}",
    )
    resp = auth_client(admin_staff).get(f"{URL}?q=uniquewechat_{suffix}")
    ids = [r["id"] for r in resp.json()["results"]]
    assert u.id in ids


def test_match_field_name(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    _user(create_customer_profile, matchmaker_staff, name="名字匹配")
    resp = auth_client(admin_staff).get(f"{URL}?q=名字匹配")
    item = resp.json()["results"][0]
    assert item["match_field"] == "name"


def test_match_field_null_without_q(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    _user(create_customer_profile, matchmaker_staff, name="无关键词")
    resp = auth_client(admin_staff).get(URL)
    item = resp.json()["results"][0]
    assert item["match_field"] is None


# ---------------------------------------------------------------------------
# pool_status 过滤
# ---------------------------------------------------------------------------

def test_filter_by_pool_status(auth_client, admin_staff, matchmaker_staff, create_customer_profile):
    u1 = _user(create_customer_profile, matchmaker_staff, pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND)
    u2 = _user(create_customer_profile, matchmaker_staff, pool_status=CustomerProfile.STATUS_NEW_PENDING)
    resp = auth_client(admin_staff).get(f"{URL}?pool_status=communicated_pending_recommend")
    ids = [r["id"] for r in resp.json()["results"]]
    assert u1.id in ids
    assert u2.id not in ids


# ---------------------------------------------------------------------------
# owner_id 过滤（仅 admin 有效）
# ---------------------------------------------------------------------------

def test_admin_filter_by_owner_id(auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff):
    other_staff = create_staff(name="其他红娘")
    u1 = _user(create_customer_profile, matchmaker_staff)
    u2 = _user(create_customer_profile, other_staff)
    resp = auth_client(admin_staff).get(f"{URL}?owner_id={matchmaker_staff.id}")
    ids = [r["id"] for r in resp.json()["results"]]
    assert u1.id in ids
    assert u2.id not in ids


# ---------------------------------------------------------------------------
# 权限范围：matchmaker 只能搜到自己有权限看的用户
# ---------------------------------------------------------------------------

def test_matchmaker_only_sees_own_and_match_card_users(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """matchmaker 看不到其他红娘负责的、且与自己无关配对卡的用户。"""
    other_staff = create_staff(name="无关红娘")
    own_user = _user(create_customer_profile, matchmaker_staff, name="自己的用户")
    other_user = _user(create_customer_profile, other_staff, name="无关红娘的用户")

    resp = auth_client(matchmaker_staff).get(URL)
    ids = [r["id"] for r in resp.json()["results"]]
    assert own_user.id in ids
    assert other_user.id not in ids


def test_matchmaker_sees_match_card_related_user(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """matchmaker 作为配对卡 male_staff，可以看到该配对卡的 female_user。"""
    female_staff = create_staff(name="女方红娘")
    male, female = _make_mc_pair(create_customer_profile, matchmaker_staff, female_staff)
    _match_card(male, female, matchmaker_staff, female_staff)

    resp = auth_client(matchmaker_staff).get(URL)
    ids = [r["id"] for r in resp.json()["results"]]
    assert female.id in ids


# ---------------------------------------------------------------------------
# active_match_card_id
# ---------------------------------------------------------------------------

def test_active_match_card_id_populated(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    female_staff = create_staff(name="女方红娘")
    male, female = _make_mc_pair(create_customer_profile, matchmaker_staff, female_staff)
    mc = _match_card(male, female, matchmaker_staff, female_staff)

    resp = auth_client(admin_staff).get(f"{URL}?q={male.name}")
    item = next((r for r in resp.json()["results"] if r["id"] == male.id), None)
    assert item is not None
    assert item["active_match_card_id"] == mc.id


def test_active_match_card_id_null_when_no_active_card(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile
):
    u = _user(create_customer_profile, matchmaker_staff, name="无配对卡用户")
    resp = auth_client(admin_staff).get(f"{URL}?q=无配对卡用户")
    item = resp.json()["results"][0]
    assert item["active_match_card_id"] is None


# ---------------------------------------------------------------------------
# admin 看全局
# ---------------------------------------------------------------------------

def test_admin_sees_all_users(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="其他红娘")
    u1 = _user(create_customer_profile, matchmaker_staff, name="全局用户A")
    u2 = _user(create_customer_profile, other_staff, name="全局用户B")
    resp = auth_client(admin_staff).get(URL)
    ids = [r["id"] for r in resp.json()["results"]]
    assert u1.id in ids
    assert u2.id in ids
