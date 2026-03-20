"""
paid_at 与 first_meet reminder 链路集成测试

验证：
- 用户创建时 paid_at 默认为空
- PATCH 写入 paid_at 后，扫描任务能正常生成提醒
- paid_at 为空时扫描不触发任何 first_meet 类型提醒
- paid_at 写入达到各阈值后触发正确级别提醒
- 覆盖完整链路：API 写入 → 扫描 → 提醒落库

关联规则：BR-USER-006、BR-REMIND-001
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reminder.models import Reminder
from apps.reminder.services import scan_first_meet_reminders
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db

# ---------------------------------------------------------------------------
# paid_at 创建时默认行为
# ---------------------------------------------------------------------------

def test_create_user_without_paid_at_defaults_to_null(auth_client, matchmaker_staff, create_payment_level):
    """创建用户不传 paid_at → 返回值为 null，模型字段为 NULL。"""
    pl = create_payment_level()
    resp = auth_client(matchmaker_staff).post(
        "/api/v1/users/",
        {
            "name": "未付费测试用户",
            "gender": "male",
            "age": 28,
            "phone": "13800000991",
            "city": "成都",
            "basic_requirement": "随缘",
            "owner_id": matchmaker_staff.id,
            "payment_level_id": pl.id,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["paid_at"] is None
    user = CustomerProfile.objects.get(id=resp.data["id"])
    assert user.paid_at is None


def test_create_user_with_paid_at_stores_correctly(auth_client, matchmaker_staff, create_payment_level):
    """创建用户时传入 paid_at → 模型字段正确写入。"""
    pl = create_payment_level()
    paid_time = (timezone.now() - timedelta(days=2)).isoformat()
    resp = auth_client(matchmaker_staff).post(
        "/api/v1/users/",
        {
            "name": "创建时付费测试用户",
            "gender": "male",
            "age": 29,
            "phone": "13800000992",
            "city": "成都",
            "basic_requirement": "随缘",
            "owner_id": matchmaker_staff.id,
            "payment_level_id": pl.id,
            "paid_at": paid_time,
        },
        format="json",
    )
    assert resp.status_code == 201
    user = CustomerProfile.objects.get(id=resp.data["id"])
    assert user.paid_at is not None


# ---------------------------------------------------------------------------
# paid_at 写入 → 扫描链路
# ---------------------------------------------------------------------------

def test_paid_at_null_scan_generates_no_first_meet_reminder(
    auth_client, matchmaker_staff, create_customer_profile
):
    """paid_at 为 NULL 的用户，扫描任务不生成任何 first_meet 提醒。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        paid_at=None,
    )

    count = scan_first_meet_reminders()

    assert count == 0
    assert not Reminder.objects.filter(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        remind_type__in=[
            Reminder.TYPE_NORMAL,
            Reminder.TYPE_FIRST_MEET_PENDING,
            Reminder.TYPE_FIRST_MEET_DELAYED,
            Reminder.TYPE_FIRST_MEET_WARNING,
            Reminder.TYPE_FIRST_MEET_OVERDUE,
        ],
    ).exists()


def test_patch_paid_at_then_scan_generates_first_meet_pending(
    auth_client, matchmaker_staff, create_customer_profile
):
    """
    完整链路：
    用户创建时 paid_at = NULL →
    PATCH 写入 paid_at = 2 天前 →
    scan_first_meet_reminders() →
    生成 first_meet_pending 提醒
    """
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        paid_at=None,
    )

    # 先确认 paid_at 为 NULL 时扫描不产生提醒
    assert scan_first_meet_reminders() == 0

    # 通过 PATCH API 写入 paid_at（2 天前）
    paid_time = (timezone.now() - timedelta(days=2)).isoformat()
    resp = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"paid_at": paid_time},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.paid_at is not None

    # 扫描任务现在应当为此用户生成 first_meet_pending
    count = scan_first_meet_reminders()
    assert count == 1
    reminder = Reminder.objects.get(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
    )
    assert reminder.remind_type == Reminder.TYPE_FIRST_MEET_PENDING
    assert reminder.status == Reminder.STATUS_PENDING
    assert reminder.staff_id == matchmaker_staff.id
    assert reminder.is_manual is False


def test_patch_paid_at_5days_ago_then_scan_generates_overdue(
    auth_client, matchmaker_staff, create_customer_profile
):
    """
    PATCH 写入 paid_at = 5 天前 → 扫描生成 first_meet_overdue（最高优先级）。
    验证优先级规则：只生成最高阈值对应的提醒类型。
    """
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        paid_at=None,
    )

    paid_time = (timezone.now() - timedelta(days=5)).isoformat()
    resp = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"paid_at": paid_time},
        format="json",
    )
    assert resp.status_code == 200

    count = scan_first_meet_reminders()
    assert count == 1
    reminders = list(
        Reminder.objects.filter(
            target_type=Reminder.TARGET_USER,
            target_id=user.id,
        ).values_list("remind_type", flat=True)
    )
    # 只应生成一条 overdue，不能同时生成低阈值提醒
    assert reminders == [Reminder.TYPE_FIRST_MEET_OVERDUE]


def test_scan_response_in_response_includes_paid_at(
    auth_client, matchmaker_staff, create_customer_profile
):
    """PATCH 写入 paid_at 后，详情接口能返回 paid_at 字段。"""
    user = create_customer_profile(
        owner=matchmaker_staff,
        paid_at=None,
    )
    paid_time = timezone.now() - timedelta(days=1)
    resp = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"paid_at": paid_time.isoformat()},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["paid_at"] is not None

    # GET detail 也应返回 paid_at
    detail_resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")
    assert detail_resp.status_code == 200
    assert detail_resp.data["paid_at"] is not None


# ---------------------------------------------------------------------------
# paid_at 各阈值分级测试（通过 API PATCH 写入，覆盖创建 + 扫描全链路）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("days_ago,expected_type", [
    (1, Reminder.TYPE_NORMAL),
    (2, Reminder.TYPE_FIRST_MEET_PENDING),
    (3, Reminder.TYPE_FIRST_MEET_DELAYED),
    (4, Reminder.TYPE_FIRST_MEET_WARNING),
    (5, Reminder.TYPE_FIRST_MEET_OVERDUE),
])
def test_patch_paid_at_threshold_generates_correct_reminder_type(
    auth_client, matchmaker_staff, create_customer_profile, days_ago, expected_type
):
    """
    通过 API 设置 paid_at 后，按天数生成正确提醒类型（全链路参数化）。
    paid_at=T+N 天前 → scan → 预期提醒类型。
    """
    # 用不同 phone 避免 unique 冲突
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        paid_at=None,
    )
    paid_time = (timezone.now() - timedelta(days=days_ago)).isoformat()
    patch_resp = auth_client(matchmaker_staff).patch(
        f"/api/v1/users/{user.id}/",
        {"paid_at": paid_time},
        format="json",
    )
    assert patch_resp.status_code == 200

    count = scan_first_meet_reminders()
    assert count == 1
    r = Reminder.objects.get(target_type=Reminder.TARGET_USER, target_id=user.id)
    assert r.remind_type == expected_type
