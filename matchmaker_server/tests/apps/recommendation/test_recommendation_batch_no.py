"""
batch_no 生成逻辑与唯一约束测试

验证：
- 正常创建时 batch_no 格式符合 REC-YYYYMMDD-NNN 规范
- 同日第二个批次序号递增
- DB 层唯一约束（模型/migration 已有 unique=True，测试确认落库行为）
- _generate_batch_no 在已有序号存在时从正确序号开始
- batch_no 冲突时重试逻辑生效，最终成功写入
"""
import re
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.recommendation.models import RecommendationBatch
from apps.recommendation.services import (
    _MAX_BATCH_NO_RETRIES,
    _generate_batch_no,
    create_recommendation_batch,
)
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ready_user(matchmaker_staff, create_customer_profile, create_payment_level):
    pl = create_payment_level(recommend_limit=5)
    user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        payment_level=pl,
    )
    return user


@pytest.fixture
def female_candidate(create_customer_profile, create_staff):
    staff = create_staff(name="候选人红娘BN")
    return create_customer_profile(
        name="候选人甲BN",
        gender=CustomerProfile.GENDER_FEMALE,
        owner=staff,
    )


@pytest.fixture
def female_candidate2(create_customer_profile, create_staff):
    staff = create_staff(name="候选人红娘BN2")
    return create_customer_profile(
        name="候选人乙BN",
        gender=CustomerProfile.GENDER_FEMALE,
        owner=staff,
    )


# ---------------------------------------------------------------------------
# batch_no 格式
# ---------------------------------------------------------------------------

def test_batch_no_format_matches_rec_yyyymmdd_nnn(
    matchmaker_staff, ready_user, female_candidate
):
    """正常创建推荐批次时 batch_no 格式为 REC-YYYYMMDD-NNN。"""
    batch, _ = create_recommendation_batch(
        actor=matchmaker_staff,
        user_id=ready_user.id,
        candidate_user_ids=[female_candidate.id],
    )
    assert re.fullmatch(r"REC-\d{8}-\d{3}", batch.batch_no), (
        f"batch_no 格式不符合规范: {batch.batch_no}"
    )


def test_batch_no_contains_today_date(matchmaker_staff, ready_user, female_candidate):
    """batch_no 中的日期部分与当日一致。"""
    today_str = timezone.now().strftime("%Y%m%d")
    batch, _ = create_recommendation_batch(
        actor=matchmaker_staff,
        user_id=ready_user.id,
        candidate_user_ids=[female_candidate.id],
    )
    assert today_str in batch.batch_no


# ---------------------------------------------------------------------------
# 序号递增
# ---------------------------------------------------------------------------

def test_generate_batch_no_starts_at_001_for_new_date():
    """当日无批次时，序号从 001 开始。"""
    result = _generate_batch_no("20991231")
    assert result == "REC-20991231-001"


def test_generate_batch_no_increments_past_existing(create_staff, create_customer_profile):
    """已存在序号 001 时，下一个为 002。"""
    user = create_customer_profile()
    staff = create_staff(name="序号测试红娘")
    RecommendationBatch.objects.create(
        user=user, staff=staff, batch_no="REC-20991231-001"
    )
    result = _generate_batch_no("20991231")
    assert result == "REC-20991231-002"


def test_generate_batch_no_skips_gaps(create_staff, create_customer_profile):
    """已存在 001 和 003 时，跳过空缺，返回 002。"""
    user = create_customer_profile()
    staff = create_staff(name="空缺序号测试红娘")
    RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20991231-001")
    RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20991231-003")
    result = _generate_batch_no("20991231")
    assert result == "REC-20991231-002"


# ---------------------------------------------------------------------------
# batch_no 唯一约束 — DB 层
# ---------------------------------------------------------------------------

def test_batch_no_unique_constraint_raises_integrity_error(create_staff, create_customer_profile):
    """DB 层 unique=True：重复 batch_no 必抛 IntegrityError。"""
    user = create_customer_profile()
    staff = create_staff(name="唯一约束测试红娘")
    RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20991231-099")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecommendationBatch.objects.create(
                user=user, staff=staff, batch_no="REC-20991231-099"
            )


# ---------------------------------------------------------------------------
# 冲突重试逻辑
# ---------------------------------------------------------------------------

def test_batch_no_conflict_retried_and_succeeds(
    matchmaker_staff, ready_user, female_candidate, create_staff, create_customer_profile
):
    """
    模拟并发冲突场景：_generate_batch_no 第一次返回已占用的 batch_no，
    触发 IntegrityError；外层重试逻辑重新调用内层函数，
    第二次 _generate_batch_no 读到已存在记录并返回下一序号，最终写入成功。
    """
    # 预先占用 batch_no，模拟并发对手已写入
    stub_user = create_customer_profile(name="冲突预占用户", phone="13900099001")
    stub_staff = create_staff(name="冲突预占红娘")
    occupied_no = "REC-20991231-001"
    RecommendationBatch.objects.create(
        user=stub_user, staff=stub_staff, batch_no=occupied_no
    )

    call_count = [0]

    def _generate_with_first_conflict(date_str):
        call_count[0] += 1
        if call_count[0] == 1:
            # 第一次强制返回已占用的号 → 触发 IntegrityError
            return occupied_no
        # 第二次走真实逻辑，会读到 001 已存在，返回 002
        from apps.recommendation.services import _generate_batch_no as _real
        # 直接计算：occupied_no 已在 DB，所以返回 002
        prefix = f"REC-{date_str}-"
        existing = set(
            RecommendationBatch.objects.filter(
                batch_no__startswith=prefix
            ).values_list("batch_no", flat=True)
        )
        seq = 1
        while f"{seq:03d}" in {no[len(prefix):] for no in existing}:
            seq += 1
        return f"{prefix}{seq:03d}"

    with patch(
        "apps.recommendation.services._generate_batch_no",
        side_effect=_generate_with_first_conflict,
    ):
        batch, _ = create_recommendation_batch(
            actor=matchmaker_staff,
            user_id=ready_user.id,
            candidate_user_ids=[female_candidate.id],
        )

    assert call_count[0] == 2
    assert batch.batch_no != occupied_no
    assert re.fullmatch(r"REC-\d{8}-\d{3}", batch.batch_no)


def test_batch_no_conflict_exhausted_retries_raises(
    matchmaker_staff, ready_user, female_candidate
):
    """
    如果重试次数耗尽（每次都冲突），最终向上抛出 IntegrityError。
    """
    with patch(
        "apps.recommendation.services._generate_batch_no",
        return_value="REC-20991231-FIXED",
    ):
        # 先用相同名字占位，让后续所有重试都失败
        stub_user = ready_user  # 随便用一个 user 对象
        stub_staff = matchmaker_staff
        RecommendationBatch.objects.create(
            user=stub_user, staff=stub_staff, batch_no="REC-20991231-FIXED"
        )

        with pytest.raises(IntegrityError):
            create_recommendation_batch(
                actor=matchmaker_staff,
                user_id=ready_user.id,
                candidate_user_ids=[female_candidate.id],
            )
