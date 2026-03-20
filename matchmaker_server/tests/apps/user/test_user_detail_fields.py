"""
测试 User Detail serializer 的 3 个计算字段：
  recent_follow_ups / active_match_card / stats
"""

import pytest
from rest_framework import status

from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


# ── recent_follow_ups ────────────────────────────────────────────────────


def test_detail_recent_follow_ups_empty_when_no_records(
    auth_client, matchmaker_staff, create_customer_profile,
):
    user = create_customer_profile(phone="13900200001")
    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["recent_follow_ups"] == []


def test_detail_recent_follow_ups_returns_latest_5_unmatched(
    auth_client, matchmaker_staff, create_customer_profile,
):
    user = create_customer_profile(phone="13900200002")
    # 创建 7 条 unmatched 跟进
    for i in range(7):
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_UNMATCHED,
            user=user,
            staff=matchmaker_staff,
            content=f"跟进内容 {i}",
        )

    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    follow_ups = resp.data["recent_follow_ups"]
    assert len(follow_ups) == 5
    # 验证按时间降序
    for i in range(len(follow_ups) - 1):
        assert follow_ups[i]["created_at"] >= follow_ups[i + 1]["created_at"]
    # 验证返回的是最新的 5 条（content 编号 6, 5, 4, 3, 2）
    assert follow_ups[0]["content"] == "跟进内容 6"


def test_detail_recent_follow_ups_excludes_matched_scene(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    """matched 场景的跟进不应出现在 recent_follow_ups 中。"""
    user = create_customer_profile(phone="13900200003", is_in_match=True)
    partner_owner = create_staff(phone="13800200001", name="对方红娘")
    partner = create_customer_profile(
        phone="13900200004",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    card = MatchCard.objects.create(
        male_user=user,
        female_user=partner,
        male_staff=matchmaker_staff,
        female_staff=partner_owner,
        primary_staff=matchmaker_staff,
    )
    # 1 条 unmatched + 1 条 matched
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        user=user,
        staff=matchmaker_staff,
        content="未配对跟进",
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        user=user,
        match_card=card,
        staff=matchmaker_staff,
        content="配对跟进",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )

    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    follow_ups = resp.data["recent_follow_ups"]
    assert len(follow_ups) == 1
    assert follow_ups[0]["content"] == "未配对跟进"


# ── active_match_card ────────────────────────────────────────────────────


def test_detail_active_match_card_null_when_no_card(
    auth_client, matchmaker_staff, create_customer_profile,
):
    user = create_customer_profile(phone="13900200010")
    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["active_match_card"] is None


def test_detail_active_match_card_returns_active_card(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    partner_owner = create_staff(phone="13800200010", name="对方红娘")
    user = create_customer_profile(phone="13900200011", is_in_match=True)
    partner = create_customer_profile(
        phone="13900200012",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    card = MatchCard.objects.create(
        male_user=user,
        female_user=partner,
        male_staff=matchmaker_staff,
        female_staff=partner_owner,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
    )

    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    active = resp.data["active_match_card"]
    assert active is not None
    assert active["id"] == card.id
    assert active["stage"] == MatchCard.STAGE_INITIAL_CONTACT
    assert active["male_user_id"] == user.id
    assert active["female_user_id"] == partner.id


def test_detail_active_match_card_excludes_ended(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    """ended 阶段的配对卡不应出现在 active_match_card。"""
    partner_owner = create_staff(phone="13800200011", name="对方红娘2")
    user = create_customer_profile(phone="13900200013")
    partner = create_customer_profile(
        phone="13900200014",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
    )
    MatchCard.objects.create(
        male_user=user,
        female_user=partner,
        male_staff=matchmaker_staff,
        female_staff=partner_owner,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_ENDED,
    )

    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["active_match_card"] is None


# ── stats ────────────────────────────────────────────────────────────────


def test_detail_stats_all_zero_when_no_data(
    auth_client, matchmaker_staff, create_customer_profile,
):
    user = create_customer_profile(phone="13900200020")
    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["stats"] == {
        "total_recommendations": 0,
        "total_meetings": 0,
        "total_match_cards": 0,
    }


def test_detail_stats_with_real_data(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    user = create_customer_profile(phone="13900200021")
    partner_owner = create_staff(phone="13800200020", name="对方红娘3")

    # 创建推荐批次 + 3 个候选人，其中 2 个 is_met=True
    batch = RecommendationBatch.objects.create(
        user=user,
        staff=matchmaker_staff,
        batch_no="B-STAT-001",
        candidate_count=3,
    )
    candidate1 = create_customer_profile(
        phone="13900200022",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
    )
    candidate2 = create_customer_profile(
        phone="13900200023",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
    )
    candidate3 = create_customer_profile(
        phone="13900200024",
        owner=partner_owner,
        gender=CustomerProfile.GENDER_FEMALE,
    )
    RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate1, is_met=True)
    RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate2, is_met=True)
    RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate3, is_met=False)

    # 创建 2 张配对卡（1 active + 1 ended）
    MatchCard.objects.create(
        male_user=user,
        female_user=candidate1,
        male_staff=matchmaker_staff,
        female_staff=partner_owner,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
    )
    MatchCard.objects.create(
        male_user=user,
        female_user=candidate2,
        male_staff=matchmaker_staff,
        female_staff=partner_owner,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_ENDED,
    )

    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    stats = resp.data["stats"]
    assert stats["total_recommendations"] == 3
    assert stats["total_meetings"] == 2
    assert stats["total_match_cards"] == 2


def test_detail_stats_counts_female_user_match_cards(
    auth_client, matchmaker_staff, create_staff, create_customer_profile,
):
    """女方用户的配对卡也应被 total_match_cards 计入。"""
    male_owner = create_staff(phone="13800200030", name="男方红娘")
    female_user = create_customer_profile(
        phone="13900200030",
        gender=CustomerProfile.GENDER_FEMALE,
        is_in_match=True,
    )
    male_user = create_customer_profile(
        phone="13900200031",
        owner=male_owner,
        gender=CustomerProfile.GENDER_MALE,
        is_in_match=True,
    )
    MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=male_owner,
        female_staff=matchmaker_staff,
        primary_staff=matchmaker_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )

    resp = auth_client(matchmaker_staff).get(f"/api/v1/users/{female_user.id}/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["stats"]["total_match_cards"] == 1
    assert resp.data["active_match_card"] is not None
    assert resp.data["active_match_card"]["female_user_id"] == female_user.id
