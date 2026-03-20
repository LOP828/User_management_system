"""
测试 User List serializer 的 priority_score 计算逻辑（BR-SORT-001 / BR-SORT-002）。
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ── 基础分数 ──────────────────────────────────────────────────────────────


def test_new_user_without_paid_at_gets_homepage_weight_plus_new_bonus(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """无 paid_at、入库 ≤7 天 → score = homepage_weight + 15。"""
    pl = create_payment_level(homepage_weight=30)
    user = create_customer_profile(
        phone="13900300001",
        payment_level=pl,
        paid_at=None,
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    assert item["priority_score"] == 30 + 15


def test_old_user_without_paid_at_gets_only_homepage_weight(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """无 paid_at、入库 >7 天 → score = homepage_weight，无新用户加分。"""
    pl = create_payment_level(homepage_weight=20)
    user = create_customer_profile(
        phone="13900300002",
        payment_level=pl,
        paid_at=None,
    )
    # 把 created_at 手动回拨到 10 天前
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=10),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    assert item["priority_score"] == 20


# ── overdue_days 影响 ─────────────────────────────────────────────────────


def test_overdue_days_adds_10_per_day(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """paid_at 超时 3 天 → overdue_days=3，加 30 分。"""
    pl = create_payment_level(homepage_weight=10, followup_timeout_days=7)
    # paid_at 设为 10 天前 → elapsed=10, overdue=10-7=3
    user = create_customer_profile(
        phone="13900300003",
        payment_level=pl,
        paid_at=timezone.now() - timedelta(days=10),
    )
    # 回拨 created_at 避免新用户加分
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    # 10 (weight) + 3 * 10 (overdue) = 40
    assert item["priority_score"] == 40


def test_no_overdue_when_within_timeout(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """paid_at 在 timeout 范围内 → overdue_days ≤ 0，无超时加分。"""
    pl = create_payment_level(homepage_weight=10, followup_timeout_days=7)
    # paid_at 5 天前 → elapsed=5, overdue=5-7=-2
    user = create_customer_profile(
        phone="13900300004",
        payment_level=pl,
        paid_at=timezone.now() - timedelta(days=5),
    )
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    assert item["priority_score"] == 10


# ── payment_level 权重 ───────────────────────────────────────────────────


def test_higher_homepage_weight_gives_higher_score(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """不同付费等级 homepage_weight 直接影响基础分。"""
    pl_low = create_payment_level(name="基础会员", homepage_weight=10)
    pl_high = create_payment_level(name="高级会员", homepage_weight=80)

    user_low = create_customer_profile(
        phone="13900300010",
        payment_level=pl_low,
        paid_at=None,
    )
    user_high = create_customer_profile(
        phone="13900300011",
        payment_level=pl_high,
        paid_at=None,
    )
    # 回拨 created_at 去掉新用户加分
    CustomerProfile.objects.filter(id__in=[user_low.id, user_high.id]).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    scores = {r["id"]: r["priority_score"] for r in resp.data["results"]}
    assert scores[user_low.id] == 10
    assert scores[user_high.id] == 80


# ── BR-SORT-002 保底 80 分 ───────────────────────────────────────────────


def test_overdue_7_days_guarantees_min_80(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """
    overdue_days >= 7 时，score 保底 80。
    低权重 + 刚好 overdue=7 → 10 + 70 = 80，正好等于保底线。
    """
    pl = create_payment_level(homepage_weight=10, followup_timeout_days=7)
    # paid_at 14 天前 → elapsed=14, overdue=14-7=7
    user = create_customer_profile(
        phone="13900300020",
        payment_level=pl,
        paid_at=timezone.now() - timedelta(days=14),
    )
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    # 10 + 7*10 = 80, max(80, 80) = 80
    assert item["priority_score"] == 80


def test_overdue_7_days_with_zero_weight_still_gets_80(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """
    即使 homepage_weight=0，overdue_days=7 也保底 80 分。
    正常计算: 0 + 7*10 = 70，但保底规则 → max(70, 80) = 80。
    """
    pl = create_payment_level(homepage_weight=0, followup_timeout_days=3)
    # paid_at 10 天前 → elapsed=10, overdue=10-3=7
    user = create_customer_profile(
        phone="13900300021",
        payment_level=pl,
        paid_at=timezone.now() - timedelta(days=10),
    )
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    assert item["priority_score"] == 80


def test_overdue_6_days_does_not_trigger_min_80(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """overdue_days=6 不触发保底规则。"""
    pl = create_payment_level(homepage_weight=0, followup_timeout_days=7)
    # paid_at 13 天前 → elapsed=13, overdue=13-7=6
    user = create_customer_profile(
        phone="13900300022",
        payment_level=pl,
        paid_at=timezone.now() - timedelta(days=13),
    )
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=timezone.now() - timedelta(days=30),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    # 0 + 6*10 = 60，不保底
    assert item["priority_score"] == 60


# ── 边界场景 ──────────────────────────────────────────────────────────────


def test_new_user_no_overdue_no_risk(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """全新用户：无 paid_at、入库 ≤7 天、无风险 → score = weight + 15。"""
    pl = create_payment_level(homepage_weight=50)
    user = create_customer_profile(
        phone="13900300030",
        payment_level=pl,
        paid_at=None,
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    assert item["priority_score"] == 65


def test_combined_new_user_with_overdue(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level,
):
    """新用户 + 有超时（入库和付款同一天，7天内但超时）→ weight + overdue*10 + 15。"""
    pl = create_payment_level(homepage_weight=10, followup_timeout_days=3)
    # paid_at 5 天前、created_at 也是 5 天前 → 入库 ≤7 天，overdue=5-3=2
    now = timezone.now()
    user = create_customer_profile(
        phone="13900300031",
        payment_level=pl,
        paid_at=now - timedelta(days=5),
    )
    CustomerProfile.objects.filter(id=user.id).update(
        created_at=now - timedelta(days=5),
    )

    resp = auth_client(matchmaker_staff).get("/api/v1/users/")

    assert resp.status_code == status.HTTP_200_OK
    item = next(r for r in resp.data["results"] if r["id"] == user.id)
    # 10 + 2*10 + 15 = 45
    assert item["priority_score"] == 45
