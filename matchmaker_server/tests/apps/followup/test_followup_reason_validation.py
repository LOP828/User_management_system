"""
跟进记录 failure_reason_id / overdue_reason_id 语义校验测试

验证：
- 合法 reason_id 正常写入
- 非法 category 返回 INVALID_REASON_CATEGORY
- 不存在的 ID 返回 REASON_NOT_FOUND
- 已停用的 reason 返回 REASON_NOT_FOUND
- 非 unmatched 场景传 reason_id 返回 FAILURE_REASON_NOT_ALLOWED / OVERDUE_REASON_NOT_ALLOWED
"""
import pytest
from uuid import uuid4

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# failure_reason_id — 合法路径
# ---------------------------------------------------------------------------

def test_unmatched_followup_valid_failure_reason_saves_correctly(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """合法 meet_failure reason → 201，failure_reason_id 写入。"""
    user = create_customer_profile(owner=matchmaker_staff)
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_MEET_FAILURE, label="性格不合")

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "首次见面性格不合", "failure_reason_id": reason.id},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["failure_reason_id"] == reason.id


# ---------------------------------------------------------------------------
# failure_reason_id — 非法 category
# ---------------------------------------------------------------------------

def test_failure_reason_wrong_category_returns_invalid_reason_category(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """传入 pause 分类的 reason → 400，提示 INVALID_REASON_CATEGORY。"""
    user = create_customer_profile(owner=matchmaker_staff)
    wrong_reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="忙工作")

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "failure_reason_id": wrong_reason.id},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["failure_reason_id"][0]
    assert "INVALID_REASON_CATEGORY" in detail


def test_failure_reason_overdue_category_returns_invalid_reason_category(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """传入 overdue 分类的 reason → 400，提示 INVALID_REASON_CATEGORY。"""
    user = create_customer_profile(owner=matchmaker_staff)
    wrong_reason = create_reason_enum(category=ReasonEnum.CATEGORY_OVERDUE, label="用户拖延")

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "failure_reason_id": wrong_reason.id},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["failure_reason_id"][0]
    assert "INVALID_REASON_CATEGORY" in detail


# ---------------------------------------------------------------------------
# failure_reason_id — 不存在 / 已停用
# ---------------------------------------------------------------------------

def test_failure_reason_nonexistent_id_returns_reason_not_found(
    auth_client, matchmaker_staff, create_customer_profile
):
    """传入不存在的 ID → 400，提示 REASON_NOT_FOUND。"""
    user = create_customer_profile(owner=matchmaker_staff)

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "failure_reason_id": 999999},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["failure_reason_id"][0]
    assert "REASON_NOT_FOUND" in detail


def test_failure_reason_inactive_id_returns_reason_not_found(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """传入已停用的 meet_failure reason → 400，提示 REASON_NOT_FOUND。"""
    user = create_customer_profile(owner=matchmaker_staff)
    inactive_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_MEET_FAILURE, label="性格不合", is_active=False
    )

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "failure_reason_id": inactive_reason.id},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["failure_reason_id"][0]
    assert "REASON_NOT_FOUND" in detail


# ---------------------------------------------------------------------------
# failure_reason_id — 非 unmatched 场景
# ---------------------------------------------------------------------------

@pytest.fixture
def create_match_card_for_reason(create_customer_profile, create_staff):
    def factory():
        suffix = f"{uuid4().int % 10**8:08d}"
        male_staff = create_staff(name=f"男方红娘R{suffix}")
        female_staff = create_staff(name=f"女方红娘R{suffix}")
        male_user = create_customer_profile(
            owner=male_staff, gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}", is_in_match=True,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        )
        female_user = create_customer_profile(
            owner=female_staff, gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}", is_in_match=True,
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        )
        return MatchCard.objects.create(
            male_user=male_user, female_user=female_user,
            male_staff=male_staff, female_staff=female_staff,
            primary_staff=male_staff,
            stage=MatchCard.STAGE_INITIAL_CONTACT,
            risk_level=MatchCard.RISK_NONE,
        )
    return factory


def test_failure_reason_not_allowed_in_matched_scene(
    auth_client, create_match_card_for_reason, create_reason_enum, create_staff
):
    """matched 场景传 failure_reason_id → 400，提示 FAILURE_REASON_NOT_ALLOWED。"""
    card = create_match_card_for_reason()
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_MEET_FAILURE, label="性格不合")

    resp = auth_client(card.male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "回访内容",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "default",
            "failure_reason_id": reason.id,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["failure_reason_id"][0]
    assert "FAILURE_REASON_NOT_ALLOWED" in detail


def test_failure_reason_not_allowed_in_success_followup_scene(
    auth_client, create_match_card_for_reason, create_reason_enum
):
    """success_followup 场景传 failure_reason_id → 400，提示 FAILURE_REASON_NOT_ALLOWED。"""
    card = create_match_card_for_reason()
    card.stage = MatchCard.STAGE_SUCCESS
    card.save(update_fields=["stage", "updated_at"])
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_MEET_FAILURE, label="性格不合")

    resp = auth_client(card.primary_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "content": "成功后回访",
            "is_still_contact": "yes",
            "next_remind_mode": "default",
            "failure_reason_id": reason.id,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["failure_reason_id"][0]
    assert "FAILURE_REASON_NOT_ALLOWED" in detail


# ---------------------------------------------------------------------------
# overdue_reason_id — 非法 category
# ---------------------------------------------------------------------------

def test_overdue_reason_wrong_category_returns_invalid_reason_category(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """overdue_reason_id 传入 pause 分类 → 400，提示 INVALID_REASON_CATEGORY。"""
    user = create_customer_profile(owner=matchmaker_staff)
    wrong_reason = create_reason_enum(category=ReasonEnum.CATEGORY_PAUSE, label="忙工作")

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "overdue_reason_id": wrong_reason.id},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["overdue_reason_id"][0]
    assert "INVALID_REASON_CATEGORY" in detail


def test_overdue_reason_meet_failure_category_returns_invalid_reason_category(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """overdue_reason_id 传入 meet_failure 分类 → 400，提示 INVALID_REASON_CATEGORY。"""
    user = create_customer_profile(owner=matchmaker_staff)
    wrong_reason = create_reason_enum(category=ReasonEnum.CATEGORY_MEET_FAILURE, label="性格不合")

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "overdue_reason_id": wrong_reason.id},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["overdue_reason_id"][0]
    assert "INVALID_REASON_CATEGORY" in detail


# ---------------------------------------------------------------------------
# overdue_reason_id — 不存在
# ---------------------------------------------------------------------------

def test_overdue_reason_nonexistent_id_returns_reason_not_found(
    auth_client, matchmaker_staff, create_customer_profile
):
    """overdue_reason_id 传入不存在的 ID → 400，提示 REASON_NOT_FOUND。"""
    user = create_customer_profile(owner=matchmaker_staff)

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {"scene": "unmatched", "user_id": user.id, "content": "...", "overdue_reason_id": 999998},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["overdue_reason_id"][0]
    assert "REASON_NOT_FOUND" in detail


# ---------------------------------------------------------------------------
# overdue_reason_id — 非 unmatched 场景
# ---------------------------------------------------------------------------

def test_overdue_reason_not_allowed_in_matched_scene(
    auth_client, create_match_card_for_reason, create_reason_enum
):
    """matched 场景传 overdue_reason_id → 400，提示 OVERDUE_REASON_NOT_ALLOWED。"""
    card = create_match_card_for_reason()
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_OVERDUE, label="用户拖延")

    resp = auth_client(card.male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "回访内容",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "default",
            "overdue_reason_id": reason.id,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["overdue_reason_id"][0]
    assert "OVERDUE_REASON_NOT_ALLOWED" in detail


# ---------------------------------------------------------------------------
# overdue_reason_note — 场景限制
# ---------------------------------------------------------------------------

def test_overdue_reason_note_allowed_in_unmatched_scene(
    auth_client, matchmaker_staff, create_customer_profile, create_reason_enum
):
    """unmatched 场景可以正常传入 overdue_reason_note。"""
    user = create_customer_profile(owner=matchmaker_staff)
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_OVERDUE, label="库存不足")

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "unmatched",
            "user_id": user.id,
            "content": "处理超时提醒",
            "overdue_reason_id": reason.id,
            "overdue_reason_note": "已重新安排推荐计划",
        },
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["overdue_reason_id"] == reason.id
    assert resp.data["overdue_reason_note"] == "已重新安排推荐计划"


def test_overdue_reason_note_not_allowed_in_matched_scene(
    auth_client, create_match_card_for_reason
):
    """matched 场景传 overdue_reason_note → 400，提示 OVERDUE_REASON_NOTE_NOT_ALLOWED。"""
    card = create_match_card_for_reason()

    resp = auth_client(card.male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "回访内容",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "default",
            "overdue_reason_note": "不应该出现在 matched 场景",
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["overdue_reason_note"][0]
    assert "OVERDUE_REASON_NOTE_NOT_ALLOWED" in detail


def test_overdue_reason_note_not_allowed_in_success_followup_scene(
    auth_client, create_match_card_for_reason
):
    """success_followup 场景传 overdue_reason_note → 400，提示 OVERDUE_REASON_NOTE_NOT_ALLOWED。"""
    card = create_match_card_for_reason()
    card.stage = MatchCard.STAGE_SUCCESS
    card.save(update_fields=["stage", "updated_at"])

    resp = auth_client(card.primary_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "content": "成功后回访",
            "is_still_contact": "yes",
            "next_remind_mode": "default",
            "overdue_reason_note": "不应该出现在 success_followup 场景",
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION_ERROR"
    detail = resp.data["details"]["overdue_reason_note"][0]
    assert "OVERDUE_REASON_NOTE_NOT_ALLOWED" in detail


def test_overdue_reason_note_without_overdue_reason_id_in_unmatched_scene(
    auth_client, matchmaker_staff, create_customer_profile
):
    """unmatched 场景只传 overdue_reason_note 不传 overdue_reason_id → 允许（note 是选填补充字段）。"""
    user = create_customer_profile(owner=matchmaker_staff)

    resp = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "unmatched",
            "user_id": user.id,
            "content": "普通跟进备注",
            "overdue_reason_note": "仅备注无 reason_id",
        },
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["overdue_reason_note"] == "仅备注无 reason_id"
    assert resp.data["overdue_reason_id"] is None
