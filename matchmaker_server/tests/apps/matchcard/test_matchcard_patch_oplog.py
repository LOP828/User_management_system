"""
测试 PATCH /match-cards/{id}/ 的 operation_log 审计日志。
"""

from uuid import uuid4

import pytest

from apps.matchcard.models import MatchCard
from apps.oplog.models import OperationLog
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


@pytest.fixture
def create_match_card(create_customer_profile, create_staff):
    def factory(**kwargs):
        male_staff = kwargs.pop("male_staff", None) or create_staff(name="男方红娘")
        female_staff = kwargs.pop("female_staff", None) or create_staff(name="女方红娘")
        primary_staff = kwargs.pop("primary_staff", None) or male_staff
        suffix = f"{uuid4().int % 10**8:08d}"
        male_user = kwargs.pop("male_user", None) or create_customer_profile(
            owner=male_staff,
            gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}",
            wechat=f"m_{suffix}",
            is_in_match=True,
        )
        female_user = kwargs.pop("female_user", None) or create_customer_profile(
            owner=female_staff,
            gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}",
            wechat=f"f_{suffix}",
            is_in_match=True,
        )
        defaults = {
            "male_user": male_user,
            "female_user": female_user,
            "male_staff": male_staff,
            "female_staff": female_staff,
            "primary_staff": primary_staff,
            "stage": MatchCard.STAGE_INITIAL_CONTACT,
        }
        defaults.update(kwargs)
        return MatchCard.objects.create(**defaults)

    return factory


# ── male_feedback 写日志 ─────────────────────────────────────────────────


def test_patch_male_feedback_creates_oplog(
    auth_client, create_match_card, create_staff,
):
    male_staff = create_staff(name="男方红娘A")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)

    resp = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {"male_feedback": "男方觉得不错"},
        format="json",
    )

    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).latest("id")
    assert log.operator_id == male_staff.id
    assert log.before_json["male_feedback"] is None
    assert log.after_json["male_feedback"] == "男方觉得不错"


# ── female_feedback 写日志 ───────────────────────────────────────────────


def test_patch_female_feedback_creates_oplog(
    auth_client, create_match_card, create_staff,
):
    female_staff = create_staff(name="女方红娘B")
    card = create_match_card(female_staff=female_staff)

    resp = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {"female_feedback": "女方很满意"},
        format="json",
    )

    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).latest("id")
    assert log.operator_id == female_staff.id
    assert log.before_json["female_feedback"] is None
    assert log.after_json["female_feedback"] == "女方很满意"


# ── heat 写日志 ──────────────────────────────────────────────────────────


def test_patch_heat_creates_oplog(
    auth_client, create_match_card, create_staff,
):
    male_staff = create_staff(name="男方红娘C")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)

    resp = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {"male_heat": 8},
        format="json",
    )

    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).latest("id")
    assert log.before_json["male_heat"] is None
    assert log.after_json["male_heat"] == 8


# ── staff_judgment 写日志 ────────────────────────────────────────────────


def test_patch_staff_judgment_creates_oplog(
    auth_client, create_match_card, create_staff,
):
    primary = create_staff(name="主操作红娘D")
    card = create_match_card(primary_staff=primary, male_staff=primary)

    resp = auth_client(primary).patch(
        f"/api/v1/match-cards/{card.id}/",
        {"staff_judgment": "双方关系稳定"},
        format="json",
    )

    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).latest("id")
    assert log.operator_id == primary.id
    assert log.before_json["staff_judgment"] is None
    assert log.after_json["staff_judgment"] == "双方关系稳定"


# ── 多字段同时修改 ───────────────────────────────────────────────────────


def test_patch_multiple_fields_logs_all_changes(
    auth_client, create_match_card, create_staff,
):
    primary = create_staff(name="主操作红娘E")
    card = create_match_card(primary_staff=primary, male_staff=primary)

    resp = auth_client(primary).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "male_feedback": "聊得不错",
            "male_heat": 9,
            "staff_judgment": "进展顺利",
        },
        format="json",
    )

    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).latest("id")
    assert "male_feedback" in log.before_json
    assert "male_heat" in log.before_json
    assert "staff_judgment" in log.before_json
    assert log.after_json["male_feedback"] == "聊得不错"
    assert log.after_json["male_heat"] == 9
    assert log.after_json["staff_judgment"] == "进展顺利"


# ── 无实际变更不写日志 ───────────────────────────────────────────────────


def test_patch_same_value_does_not_create_oplog(
    auth_client, create_match_card, create_staff,
):
    """提交的值与当前值完全相同时，不应产生日志。"""
    primary = create_staff(name="主操作红娘F")
    card = create_match_card(
        primary_staff=primary,
        male_staff=primary,
        male_feedback="已有反馈",
        male_heat=7,
    )
    count_before = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).count()

    resp = auth_client(primary).patch(
        f"/api/v1/match-cards/{card.id}/",
        {"male_feedback": "已有反馈", "male_heat": 7},
        format="json",
    )

    assert resp.status_code == 200
    count_after = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).count()
    assert count_after == count_before


# ── 部分字段变化只记录变化部分 ───────────────────────────────────────────


def test_patch_partial_change_only_logs_changed_fields(
    auth_client, create_match_card, create_staff,
):
    """多字段提交但只有部分值变化时，日志只记录变化部分。"""
    primary = create_staff(name="主操作红娘G")
    card = create_match_card(
        primary_staff=primary,
        male_staff=primary,
        male_feedback="旧反馈",
        male_heat=5,
    )

    resp = auth_client(primary).patch(
        f"/api/v1/match-cards/{card.id}/",
        {"male_feedback": "旧反馈", "male_heat": 9},  # feedback 没变，heat 变了
        format="json",
    )

    assert resp.status_code == 200
    log = OperationLog.objects.filter(
        target_type="match_card",
        target_id=card.id,
        action="match_card_updated",
    ).latest("id")
    assert "male_feedback" not in log.before_json
    assert "male_heat" in log.before_json
    assert log.before_json["male_heat"] == 5
    assert log.after_json["male_heat"] == 9
