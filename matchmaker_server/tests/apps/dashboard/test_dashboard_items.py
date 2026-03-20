"""
测试 Dashboard 明细列表（items）：
  unmatched_overdue / matched_pending_visit / today_processed / recent_new / overdue_summary
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db

MATCHMAKER_URL = "/api/v1/dashboard/matchmaker/"
ADMIN_URL = "/api/v1/dashboard/admin/"


def _uid():
    return f"{uuid4().int % 10**8:08d}"


def _user(create_customer_profile, owner, **kw):
    suffix = _uid()
    return create_customer_profile(owner=owner, phone=f"138{suffix}", wechat=f"wx_{suffix}", **kw)


def _make_pair(create_customer_profile, male_staff, female_staff, **card_kw):
    s1, s2 = _uid(), _uid()
    male = create_customer_profile(
        owner=male_staff, gender=CustomerProfile.GENDER_MALE,
        is_in_match=True, phone=f"139{s1}", wechat=f"m_{s1}",
    )
    female = create_customer_profile(
        owner=female_staff, gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True, phone=f"137{s2}", wechat=f"f_{s2}",
    )
    return male, female


# ── 红娘：响应结构包含新增模块 ──────────────────────────────────────────


def test_matchmaker_dashboard_has_items_sections(auth_client, matchmaker_staff):
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    data = resp.json()
    # 新增四个模块
    assert "unmatched_overdue" in data
    assert "matched_pending_visit" in data
    assert "today_processed" in data
    assert "recent_new" in data
    # 结构检查
    assert "count" in data["unmatched_overdue"]
    assert "items" in data["unmatched_overdue"]
    assert "count" in data["matched_pending_visit"]
    assert "items" in data["matched_pending_visit"]
    assert "count" in data["today_processed"]
    assert "count" in data["recent_new"]
    assert "items" in data["recent_new"]


# ── 红娘：unmatched_overdue ──────────────────────────────────────────────


def test_unmatched_overdue_empty_when_no_paid_at(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    _user(create_customer_profile, matchmaker_staff, paid_at=None)
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["unmatched_overdue"]["count"] == 0
    assert resp.json()["unmatched_overdue"]["items"] == []


def test_unmatched_overdue_empty_when_within_timeout(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    pl = create_payment_level(followup_timeout_days=7)
    _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=5),
    )
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["unmatched_overdue"]["count"] == 0


def test_unmatched_overdue_returns_overdue_user_with_correct_fields(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    pl = create_payment_level(homepage_weight=20, followup_timeout_days=7)
    user = _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl,
        paid_at=timezone.now() - timedelta(days=12),
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )
    # 回拨 created_at 去掉新用户加分
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    overdue = resp.json()["unmatched_overdue"]
    assert overdue["count"] == 1
    item = overdue["items"][0]
    assert item["user_id"] == user.id
    assert item["user_name"] == user.name
    assert item["pool_status_display"] == "已沟通待推荐"
    assert item["payment_level_name"] == pl.name
    assert item["overdue_days"] == 5  # 12 - 7
    assert item["overdue_type"] == "跟进超时"
    # priority_score = 20 (weight) + 5*10 (overdue) = 70
    assert item["priority_score"] == 70


def test_unmatched_overdue_sorted_by_priority_score_desc(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    pl_low = create_payment_level(name="基础", homepage_weight=10, followup_timeout_days=7)
    pl_high = create_payment_level(name="高级", homepage_weight=80, followup_timeout_days=7)
    user_low = _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl_low, paid_at=timezone.now() - timedelta(days=10),
    )
    user_high = _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl_high, paid_at=timezone.now() - timedelta(days=10),
    )
    # 回拨 created_at
    CustomerProfile.objects.filter(id__in=[user_low.id, user_high.id]).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    items = resp.json()["unmatched_overdue"]["items"]
    assert len(items) == 2
    # 高权重在前
    assert items[0]["user_id"] == user_high.id
    assert items[0]["priority_score"] > items[1]["priority_score"]


def test_unmatched_overdue_only_shows_own_users(
    auth_client, matchmaker_staff, create_staff, create_customer_profile, create_payment_level,
):
    """红娘只能看到自己负责的超时用户。"""
    other_staff = create_staff(name="其他红娘")
    pl = create_payment_level(followup_timeout_days=3)
    _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=10),
    )
    _user(
        create_customer_profile, other_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=10),
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["unmatched_overdue"]["count"] == 1


# ── 红娘：matched_pending_visit ──────────────────────────────────────────


def test_matched_pending_visit_empty_when_no_active_cards(
    auth_client, matchmaker_staff,
):
    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    mpv = resp.json()["matched_pending_visit"]
    assert mpv["count"] == 0
    assert mpv["items"] == []


def test_matched_pending_visit_returns_active_card_with_fields(
    auth_client, matchmaker_staff, create_staff, create_customer_profile, create_payment_level,
):
    other_staff = create_staff(name="对方红娘")
    pl = create_payment_level(homepage_weight=40)
    male, female = _make_pair(create_customer_profile, matchmaker_staff, other_staff)
    now = timezone.now()
    card = MatchCard.objects.create(
        male_user=male, female_user=female,
        male_staff=matchmaker_staff, female_staff=other_staff,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
        next_remind_at=now - timedelta(days=2),
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    mpv = resp.json()["matched_pending_visit"]
    assert mpv["count"] == 1
    item = mpv["items"][0]
    assert item["match_card_id"] == card.id
    assert item["male_name"] == male.name
    assert item["female_name"] == female.name
    assert item["stage_display"] == "初期接触"
    assert item["risk_level_display"] == "无风险"
    assert item["overdue_days"] == 2
    assert item["priority_score"] > 0


def test_matched_pending_visit_excludes_ended_cards(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    other_staff = create_staff(name="对方红娘")
    male, female = _make_pair(create_customer_profile, matchmaker_staff, other_staff)
    MatchCard.objects.create(
        male_user=male, female_user=female,
        male_staff=matchmaker_staff, female_staff=other_staff,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_ENDED,
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["matched_pending_visit"]["count"] == 0


def test_matched_pending_visit_includes_risk_weight(
    auth_client, matchmaker_staff, create_staff, create_customer_profile, create_payment_level,
):
    """高风险配对卡 priority_score 应包含 +50 风险加分。"""
    other_staff = create_staff(name="对方红娘")
    pl = create_payment_level(homepage_weight=10)
    male, female = _make_pair(create_customer_profile, matchmaker_staff, other_staff)
    MatchCard.objects.create(
        male_user=male, female_user=female,
        male_staff=matchmaker_staff, female_staff=other_staff,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
        risk_level=MatchCard.RISK_HIGH_RISK,
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    item = resp.json()["matched_pending_visit"]["items"][0]
    # score >= homepage_weight + 50 (risk)
    assert item["priority_score"] >= 50


# ── 红娘：today_processed ────────────────────────────────────────────────


def test_today_processed_counts_todays_followups(
    auth_client, matchmaker_staff, create_customer_profile,
):
    user = _user(create_customer_profile, matchmaker_staff)
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user, staff=matchmaker_staff, content="跟进1",
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user, staff=matchmaker_staff, content="跟进2",
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["today_processed"]["count"] == 2


def test_today_processed_excludes_other_staffs_followups(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    other_staff = create_staff(name="其他红娘")
    user = _user(create_customer_profile, other_staff)
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user, staff=other_staff, content="别人的跟进",
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["today_processed"]["count"] == 0


# ── 红娘：recent_new ─────────────────────────────────────────────────────


def test_recent_new_returns_users_within_7_days(
    auth_client, matchmaker_staff, create_customer_profile,
):
    recent = _user(create_customer_profile, matchmaker_staff)
    old = _user(create_customer_profile, matchmaker_staff)
    CustomerProfile.objects.filter(id=old.id).update(
        created_at=timezone.now() - timedelta(days=10),
    )

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    rn = resp.json()["recent_new"]
    assert rn["count"] == 1
    assert rn["items"][0]["user_id"] == recent.id
    assert "user_name" in rn["items"][0]
    assert "created_at" in rn["items"][0]


def test_recent_new_excludes_other_staffs_users(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    other_staff = create_staff(name="其他红娘")
    _user(create_customer_profile, matchmaker_staff)
    _user(create_customer_profile, other_staff)

    resp = auth_client(matchmaker_staff).get(MATCHMAKER_URL)
    assert resp.json()["recent_new"]["count"] == 1


# ── 管理员：overdue_summary ──────────────────────────────────────────────


def test_admin_dashboard_has_overdue_summary(auth_client, admin_staff):
    resp = auth_client(admin_staff).get(ADMIN_URL)
    data = resp.json()
    assert "overdue_summary" in data
    assert "total_overdue_users" in data["overdue_summary"]
    assert "by_staff" in data["overdue_summary"]


def test_admin_overdue_summary_counts_all_overdue_users(
    auth_client, admin_staff, matchmaker_staff, create_staff,
    create_customer_profile, create_payment_level,
):
    other_staff = create_staff(name="其他红娘")
    pl = create_payment_level(followup_timeout_days=3)
    _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=10),
    )
    _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=8),
    )
    _user(
        create_customer_profile, other_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=12),
    )
    # 非超时用户
    _user(
        create_customer_profile, matchmaker_staff,
        payment_level=pl, paid_at=timezone.now() - timedelta(days=1),
    )

    resp = auth_client(admin_staff).get(ADMIN_URL)
    summary = resp.json()["overdue_summary"]
    assert summary["total_overdue_users"] == 3
    assert len(summary["by_staff"]) == 2
    # 按 overdue_count 降序
    assert summary["by_staff"][0]["overdue_count"] >= summary["by_staff"][1]["overdue_count"]


def test_admin_overdue_summary_empty_when_no_overdue(
    auth_client, admin_staff, matchmaker_staff, create_customer_profile,
):
    _user(create_customer_profile, matchmaker_staff, paid_at=None)

    resp = auth_client(admin_staff).get(ADMIN_URL)
    summary = resp.json()["overdue_summary"]
    assert summary["total_overdue_users"] == 0
    assert summary["by_staff"] == []


# ── 管理员：已有 count 字段不受影响 ──────────────────────────────────────


def test_admin_existing_counts_still_correct(auth_client, admin_staff):
    resp = auth_client(admin_staff).get(ADMIN_URL)
    data = resp.json()
    assert "user_pool" in data
    assert "match_cards" in data
    assert "reminders" in data
    assert "pending_approvals" in data
