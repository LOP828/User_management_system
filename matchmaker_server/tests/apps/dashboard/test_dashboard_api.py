import pytest
from django.utils import timezone
from uuid import uuid4

from apps.matchcard.models import MatchCard
from apps.reminder.models import Reminder
from apps.transfer.models import UserTransferRequest
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db

MATCHMAKER_URL = "/api/v1/dashboard/matchmaker/"
ADMIN_URL = "/api/v1/dashboard/admin/"


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _user(create_customer_profile, owner, status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND, **kw):
    suffix = f"{uuid4().int % 10**8:08d}"
    return create_customer_profile(
        owner=owner,
        pool_status=status,
        phone=f"138{suffix}",
        wechat=f"wx_{suffix}",
        **kw,
    )


def _match_card(male_user, female_user, male_staff, female_staff, stage=MatchCard.STAGE_INITIAL_CONTACT, primary_staff=None):
    return MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_staff,
        female_staff=female_staff,
        primary_staff=primary_staff or male_staff,
        stage=stage,
        risk_level=MatchCard.RISK_NONE,
    )


def _make_pair(create_customer_profile, male_staff, female_staff):
    """创建一对处于 selected_pending_meet + is_in_match 状态的男女用户。"""
    suffix = f"{uuid4().int % 10**8:08d}"
    male = create_customer_profile(
        owner=male_staff,
        gender=CustomerProfile.GENDER_MALE,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
        phone=f"139{suffix}",
        wechat=f"male_{suffix}",
    )
    suffix2 = f"{uuid4().int % 10**8:08d}"
    female = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
        phone=f"137{suffix2}",
        wechat=f"female_{suffix2}",
    )
    return male, female


# ---------------------------------------------------------------------------
# 权限 — matchmaker endpoint
# ---------------------------------------------------------------------------

def test_matchmaker_dashboard_accessible_by_matchmaker(auth_client, matchmaker_staff):
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.status_code == 200


def test_matchmaker_dashboard_forbidden_for_admin(auth_client, admin_staff):
    resp = auth_client(admin_staff).get(MATCHMAKER_URL)
    assert resp.status_code == 403


def test_matchmaker_dashboard_forbidden_unauthenticated(api_client):
    resp = api_client.get(MATCHMAKER_URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 权限 — admin endpoint
# ---------------------------------------------------------------------------

def test_admin_dashboard_accessible_by_admin(auth_client, admin_staff):
    resp = auth_client(admin_staff).get(ADMIN_URL)
    assert resp.status_code == 200


def test_admin_dashboard_forbidden_for_matchmaker(auth_client, matchmaker_staff):
    resp = auth_client(matchmaker_staff).get(ADMIN_URL)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 红娘首页 — 响应结构
# ---------------------------------------------------------------------------

def test_matchmaker_dashboard_response_structure(auth_client, matchmaker_staff):
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    data = resp.json()
    assert "user_pool" in data
    assert "match_cards" in data
    assert "reminders" in data
    up = data["user_pool"]
    assert "new_pending" in up
    assert "communicated_pending_recommend" in up
    assert "recommended_pending_select" in up
    assert "selected_pending_meet" in up
    assert "met_not_continue" in up
    assert "paused" in up
    mc = data["match_cards"]
    assert "active" in mc
    assert "success_pending_review" in mc


# ---------------------------------------------------------------------------
# 红娘首页 — user_pool 只统计自己负责的用户
# ---------------------------------------------------------------------------

def test_matchmaker_user_pool_counts_own_users(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="其他红娘")
    _user(create_customer_profile, matchmaker_staff, CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND)
    _user(create_customer_profile, matchmaker_staff, CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT)
    _user(create_customer_profile, other_staff, CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND)  # 不应被计入

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    up = resp.json()["user_pool"]
    assert up["communicated_pending_recommend"] == 1
    assert up["recommended_pending_select"] == 1


# ---------------------------------------------------------------------------
# 红娘首页 — match_cards 只统计参与的配对卡
# ---------------------------------------------------------------------------

def test_matchmaker_active_match_card_count(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="其他女方红娘")
    male, female = _make_pair(create_customer_profile, matchmaker_staff, other_staff)
    _match_card(male, female, matchmaker_staff, other_staff, stage=MatchCard.STAGE_INITIAL_CONTACT)

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["match_cards"]["active"] == 1


def test_matchmaker_ended_card_not_counted_in_active(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="其他女方红娘")
    male, female = _make_pair(create_customer_profile, matchmaker_staff, other_staff)
    _match_card(male, female, matchmaker_staff, other_staff, stage=MatchCard.STAGE_ENDED)

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["match_cards"]["active"] == 0


def test_matchmaker_unrelated_card_not_counted(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """其他红娘的配对卡不应被统计进 active。"""
    other_a = create_staff(name="其他男方")
    other_b = create_staff(name="其他女方")
    male, female = _make_pair(create_customer_profile, other_a, other_b)
    _match_card(male, female, other_a, other_b, stage=MatchCard.STAGE_INITIAL_CONTACT)

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["match_cards"]["active"] == 0


# ---------------------------------------------------------------------------
# 红娘首页 — reminders 统计
# ---------------------------------------------------------------------------

def test_matchmaker_reminder_pending_count(
    auth_client, matchmaker_staff, create_customer_profile
):
    from django.utils import timezone
    user = _user(create_customer_profile, matchmaker_staff)
    Reminder.objects.create(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=matchmaker_staff,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=timezone.now(),
        status=Reminder.STATUS_PENDING,
    )
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["reminders"]["pending"] >= 1


# ---------------------------------------------------------------------------
# 管理员首页 — 响应结构
# ---------------------------------------------------------------------------

def test_admin_dashboard_response_structure(auth_client, admin_staff):
    resp = auth_client(admin_staff).get(ADMIN_URL)
    data = resp.json()
    assert "user_pool" in data
    assert "match_cards" in data
    assert "reminders" in data
    assert "pending_approvals" in data
    mc = data["match_cards"]
    assert "active" in mc
    assert "success_pending_review" in mc
    assert "success" in mc
    assert "high_risk" in mc
    pa = data["pending_approvals"]
    assert "transfer_count" in pa
    assert "success_count" in pa
    up = data["user_pool"]
    assert "new_pending" in up
    assert "paused" in up


# ---------------------------------------------------------------------------
# 管理员首页 — pending_approvals 统计
# ---------------------------------------------------------------------------

def test_admin_pending_approvals_transfer_count(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    to_staff = create_staff(name="接收红娘")
    user = _user(create_customer_profile, matchmaker_staff)
    UserTransferRequest.objects.create(
        user=user,
        from_staff=matchmaker_staff,
        to_staff=to_staff,
        reason="休假",
        status=UserTransferRequest.STATUS_PENDING,
    )
    resp = auth_client(admin_staff).get(ADMIN_URL)
    assert resp.json()["pending_approvals"]["transfer_count"] >= 1


# ---------------------------------------------------------------------------
# 管理员首页 — 全局 user_pool 统计
# ---------------------------------------------------------------------------

def test_admin_user_pool_counts_all_users(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile, create_staff
):
    """admin 的 user_pool 应包含所有红娘负责的用户，不受 staff 过滤。"""
    other_staff = create_staff(name="其他红娘")
    _user(create_customer_profile, matchmaker_staff, CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND)
    _user(create_customer_profile, other_staff, CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND)

    resp = auth_client(admin_staff).get(ADMIN_URL)
    assert resp.json()["user_pool"]["communicated_pending_recommend"] >= 2


def test_admin_user_pool_excludes_matched_and_deleted(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile
):
    _user(
        create_customer_profile,
        matchmaker_staff,
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_in_match=False,
    )
    _user(
        create_customer_profile,
        matchmaker_staff,
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_in_match=True,
    )
    _user(
        create_customer_profile,
        matchmaker_staff,
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        deleted_at=timezone.now(),
    )

    resp = auth_client(admin_staff).get(ADMIN_URL)
    assert resp.json()["user_pool"]["communicated_pending_recommend"] == 1
def test_matchmaker_match_card_counts_primary_staff(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """primary_staff 也应被纳入 active 统计。"""
    other_male = create_staff(name="其他男方")
    other_female = create_staff(name="其他女方")
    male, female = _make_pair(create_customer_profile, other_male, other_female)
    _match_card(
        male,
        female,
        male_staff=other_male,
        female_staff=other_female,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
        primary_staff=matchmaker_staff,
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["match_cards"]["active"] == 1


def test_matchmaker_user_pool_excludes_matched_and_deleted(
    auth_client, matchmaker_staff, create_customer_profile
):
    _user(
        create_customer_profile,
        matchmaker_staff,
        CustomerProfile.STATUS_NEW_PENDING,
        is_in_match=False,
    )
    _user(
        create_customer_profile,
        matchmaker_staff,
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_in_match=True,
    )
    _user(
        create_customer_profile,
        matchmaker_staff,
        CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        deleted_at=timezone.now(),
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    up = resp.json()["user_pool"]
    assert up["new_pending"] == 1
    assert up["communicated_pending_recommend"] == 0
