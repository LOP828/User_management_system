"""用户列表 ordering=priority_score 专项测试

覆盖目标：
1. priority_score 降序/升序排序
2. 不同 payment_level / overdue_days / 新用户场景下排序正确
3. 与现有 created_at 排序共存
4. 与权限过滤共存（红娘只看自己用户）
5. annotation 计算值与 serializer Python 计算一致
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


@pytest.fixture
def _users(create_customer_profile, create_payment_level, matchmaker_staff):
    """创建三个用户，priority_score 差异明确。

    返回 (low, mid, high) 三个用户，按 score 从低到高。
    - low:  homepage_weight=5,  无 overdue, 非新用户 → score=5
    - mid:  homepage_weight=30, 无 overdue, 非新用户 → score=30
    - high: homepage_weight=10, overdue=3 天, 非新用户 → score=10+30=40
    """
    now = timezone.now()
    old_date = now - timedelta(days=30)

    pl_low = create_payment_level(name="基础", homepage_weight=5, followup_timeout_days=7)
    pl_mid = create_payment_level(name="中级", homepage_weight=30, followup_timeout_days=7)
    pl_high = create_payment_level(name="高级", homepage_weight=10, followup_timeout_days=7)

    low = create_customer_profile(
        owner=matchmaker_staff, phone="13800010001", wechat="ord_low",
        payment_level=pl_low, paid_at=None,
    )
    mid = create_customer_profile(
        owner=matchmaker_staff, phone="13800010002", wechat="ord_mid",
        payment_level=pl_mid, paid_at=None,
    )
    high = create_customer_profile(
        owner=matchmaker_staff, phone="13800010003", wechat="ord_high",
        payment_level=pl_high,
        paid_at=now - timedelta(days=10),  # elapsed=10, overdue=10-7=3, +30
    )

    # 回拨 created_at 去掉新用户加分
    CustomerProfile.objects.filter(id__in=[low.id, mid.id, high.id]).update(
        created_at=old_date,
    )
    low.refresh_from_db()
    mid.refresh_from_db()
    high.refresh_from_db()

    return low, mid, high


class TestPriorityScoreOrdering:

    def test_descending_order(self, auth_client, matchmaker_staff, _users):
        low, mid, high = _users

        resp = auth_client(matchmaker_staff).get("/api/v1/users/?ordering=-priority_score")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert ids.index(high.id) < ids.index(mid.id) < ids.index(low.id)

    def test_ascending_order(self, auth_client, matchmaker_staff, _users):
        low, mid, high = _users

        resp = auth_client(matchmaker_staff).get("/api/v1/users/?ordering=priority_score")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert ids.index(low.id) < ids.index(mid.id) < ids.index(high.id)

    def test_score_values_match_between_annotation_and_serializer(
        self, auth_client, matchmaker_staff, _users
    ):
        """annotation 出的 priority_score 与 serializer Python 计算应一致。"""
        low, mid, high = _users

        resp = auth_client(matchmaker_staff).get("/api/v1/users/?ordering=-priority_score")

        scores = {r["id"]: r["priority_score"] for r in resp.data["results"]}
        assert scores[low.id] == 5
        assert scores[mid.id] == 30
        assert scores[high.id] == 40  # 10 + 3*10


class TestPriorityScoreWithNewUserBonus:

    def test_new_user_ranked_higher_than_old_user_with_same_weight(
        self, auth_client, matchmaker_staff, create_customer_profile, create_payment_level
    ):
        pl = create_payment_level(name="同级", homepage_weight=20, followup_timeout_days=7)
        old_user = create_customer_profile(
            owner=matchmaker_staff, phone="13800020001", wechat="ord_old",
            payment_level=pl, paid_at=None,
        )
        CustomerProfile.objects.filter(id=old_user.id).update(
            created_at=timezone.now() - timedelta(days=30),
        )
        new_user = create_customer_profile(
            owner=matchmaker_staff, phone="13800020002", wechat="ord_new",
            payment_level=pl, paid_at=None,
        )
        # new_user: 20 + 15 = 35, old_user: 20

        resp = auth_client(matchmaker_staff).get("/api/v1/users/?ordering=-priority_score")

        scores = {r["id"]: r["priority_score"] for r in resp.data["results"]}
        assert scores[new_user.id] == 35
        assert scores[old_user.id] == 20

        ids = [r["id"] for r in resp.data["results"]]
        assert ids.index(new_user.id) < ids.index(old_user.id)


class TestPriorityScoreOverdueFloor:

    def test_overdue_7_days_guarantees_min_80_in_ordering(
        self, auth_client, matchmaker_staff, create_customer_profile, create_payment_level
    ):
        """overdue >= 7 天保底 80 分；高 weight 无 overdue 用户排在后面。"""
        pl_low = create_payment_level(name="低权重", homepage_weight=0, followup_timeout_days=3)
        pl_high = create_payment_level(name="高权重", homepage_weight=70, followup_timeout_days=7)
        now = timezone.now()

        # overdue=7: elapsed=10, overdue=10-3=7 → base=0+70=70, 保底=max(70,80)=80
        overdue_user = create_customer_profile(
            owner=matchmaker_staff, phone="13800030001", wechat="ord_overdue",
            payment_level=pl_low,
            paid_at=now - timedelta(days=10),
        )
        # no overdue: weight=70
        rich_user = create_customer_profile(
            owner=matchmaker_staff, phone="13800030002", wechat="ord_rich",
            payment_level=pl_high, paid_at=None,
        )
        # 回拨 created_at
        CustomerProfile.objects.filter(id__in=[overdue_user.id, rich_user.id]).update(
            created_at=now - timedelta(days=30),
        )

        resp = auth_client(matchmaker_staff).get("/api/v1/users/?ordering=-priority_score")

        scores = {r["id"]: r["priority_score"] for r in resp.data["results"]}
        assert scores[overdue_user.id] == 80
        assert scores[rich_user.id] == 70
        ids = [r["id"] for r in resp.data["results"]]
        assert ids.index(overdue_user.id) < ids.index(rich_user.id)


class TestPriorityScoreWithPermissionFilter:

    def test_matchmaker_ordering_respects_ownership_filter(
        self, auth_client, create_customer_profile, create_payment_level, create_staff
    ):
        """红娘只看自己用户，ordering 不影响权限过滤。"""
        owner_a = create_staff(name="红娘A")
        owner_b = create_staff(name="红娘B")
        pl = create_payment_level(name="标准", homepage_weight=50, followup_timeout_days=7)

        user_a = create_customer_profile(
            owner=owner_a, phone="13800040001", wechat="perm_a",
            payment_level=pl, paid_at=None,
        )
        user_b = create_customer_profile(
            owner=owner_b, phone="13800040002", wechat="perm_b",
            payment_level=pl, paid_at=None,
        )

        resp = auth_client(owner_a).get("/api/v1/users/?ordering=-priority_score")

        assert resp.status_code == 200
        returned_ids = {r["id"] for r in resp.data["results"]}
        assert user_a.id in returned_ids
        assert user_b.id not in returned_ids

    def test_admin_sees_all_users_with_ordering(
        self, auth_client, admin_staff, create_customer_profile, create_payment_level, create_staff
    ):
        owner_a = create_staff(name="红娘C")
        owner_b = create_staff(name="红娘D")
        pl = create_payment_level(name="标准2", homepage_weight=20, followup_timeout_days=7)

        create_customer_profile(
            owner=owner_a, phone="13800050001", wechat="admin_ord_a",
            payment_level=pl, paid_at=None,
        )
        create_customer_profile(
            owner=owner_b, phone="13800050002", wechat="admin_ord_b",
            payment_level=pl, paid_at=None,
        )

        resp = auth_client(admin_staff).get("/api/v1/users/?ordering=-priority_score")

        assert resp.status_code == 200
        assert resp.data["count"] >= 2


class TestCreatedAtOrderingStillWorks:

    def test_created_at_ordering_not_broken(
        self, auth_client, matchmaker_staff, create_customer_profile, create_payment_level
    ):
        """确认加了 priority_score 后 created_at 排序仍正常。"""
        pl = create_payment_level(name="排序测试", homepage_weight=10)
        now = timezone.now()

        older = create_customer_profile(
            owner=matchmaker_staff, phone="13800060001", wechat="cat_older",
            payment_level=pl,
        )
        CustomerProfile.objects.filter(id=older.id).update(
            created_at=now - timedelta(days=10),
        )
        newer = create_customer_profile(
            owner=matchmaker_staff, phone="13800060002", wechat="cat_newer",
            payment_level=pl,
        )

        resp = auth_client(matchmaker_staff).get("/api/v1/users/?ordering=created_at")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert ids.index(older.id) < ids.index(newer.id)

    def test_default_ordering_is_minus_created_at(
        self, auth_client, matchmaker_staff, create_customer_profile, create_payment_level
    ):
        pl = create_payment_level(name="默认排序测试", homepage_weight=10)
        now = timezone.now()

        older = create_customer_profile(
            owner=matchmaker_staff, phone="13800070001", wechat="default_older",
            payment_level=pl,
        )
        CustomerProfile.objects.filter(id=older.id).update(
            created_at=now - timedelta(days=10),
        )
        newer = create_customer_profile(
            owner=matchmaker_staff, phone="13800070002", wechat="default_newer",
            payment_level=pl,
        )

        resp = auth_client(matchmaker_staff).get("/api/v1/users/")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert ids.index(newer.id) < ids.index(older.id)
