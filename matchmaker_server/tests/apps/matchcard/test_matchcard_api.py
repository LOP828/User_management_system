import pytest
from uuid import uuid4
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.user.models import CustomerProfile, UserStatusHistory
from apps.reminder.models import Reminder


pytestmark = pytest.mark.django_db


@pytest.fixture
def create_match_card(create_customer_profile, create_staff):
    from apps.matchcard.models import MatchCard

    def factory(**kwargs):
        male_staff = kwargs.pop("male_staff", None) or create_staff(name="男方红娘")
        female_staff = kwargs.pop("female_staff", None) or create_staff(name="女方红娘")
        primary_staff = kwargs.pop("primary_staff", None) or male_staff
        suffix = f"{uuid4().int % 10**8:08d}"
        male_user = kwargs.pop(
            "male_user",
            None,
        ) or create_customer_profile(
            owner=male_staff,
            name="男方用户",
            gender=CustomerProfile.GENDER_MALE,
            phone=f"139{suffix}",
            wechat=f"male_user_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        female_user = kwargs.pop(
            "female_user",
            None,
        ) or create_customer_profile(
            owner=female_staff,
            name="女方用户",
            gender=CustomerProfile.GENDER_FEMALE,
            phone=f"137{suffix}",
            wechat=f"female_user_{suffix}",
            pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
            is_in_match=True,
        )
        defaults = {
            "male_user": male_user,
            "female_user": female_user,
            "male_staff": male_staff,
            "female_staff": female_staff,
            "primary_staff": primary_staff,
            "stage": MatchCard.STAGE_INITIAL_CONTACT,
            "risk_level": MatchCard.RISK_NONE,
        }
        defaults.update(kwargs)
        return MatchCard.objects.create(**defaults)

    return factory


@pytest.fixture
def candidate_user(create_customer_profile, create_staff):
    staff = create_staff(name="候选人红娘matchcard")
    return create_customer_profile(
        name="候选人甲matchcard",
        gender=CustomerProfile.GENDER_FEMALE,
        owner=staff,
    )


def _prepare_user_for_recommendation(user, matchmaker_staff):
    user.owner = matchmaker_staff
    user.pool_status = CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    user.is_profile_complete = True
    user.save(update_fields=["owner", "pool_status", "is_profile_complete", "updated_at"])
    return user


def _select_recommendation_candidate(client, user, candidate_user_id):
    resp = client.post(
        "/api/v1/recommendations/",
        {
            "user_id": user.id,
            "candidate_user_ids": [candidate_user_id],
        },
        format="json",
    )
    assert resp.status_code == 201
    candidate = RecommendationCandidate.objects.get(batch__user_id=user.id, candidate_user_id=candidate_user_id)
    select_resp = client.post(f"/api/v1/recommendations/candidates/{candidate.id}/select/")
    assert select_resp.status_code == 200
    return candidate


def test_create_match_card_sets_users_in_match_and_staff_fields(auth_client, matchmaker_staff, create_customer_profile, create_staff):
    female_staff = create_staff(name="女方红娘")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        name="男方用户A",
        gender=CustomerProfile.GENDER_MALE,
        phone="13900139001",
        wechat="male_a_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        name="女方用户A",
        gender=CustomerProfile.GENDER_FEMALE,
        phone="13900139002",
        wechat="female_a_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )
    client = auth_client(matchmaker_staff)
    _prepare_user_for_recommendation(male_user, matchmaker_staff)
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)

    response = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["male_staff_id"] == matchmaker_staff.id
    assert response.data["female_staff_id"] == female_staff.id
    assert response.data["primary_staff_id"] == matchmaker_staff.id
    male_user.refresh_from_db()
    female_user.refresh_from_db()
    assert male_user.is_in_match is True
    assert female_user.is_in_match is True
    reminders = list(
        Reminder.objects.filter(
            target_type=Reminder.TARGET_MATCH_CARD,
            target_id=response.data["id"],
            status=Reminder.STATUS_PENDING,
        ).order_by("staff_id", "id")
    )
    assert len(reminders) == 2
    assert [reminder.remind_type for reminder in reminders] == [
        Reminder.TYPE_MATCHED_REVISIT,
        Reminder.TYPE_MATCHED_REVISIT,
    ]
    assert {reminder.staff_id for reminder in reminders} == {matchmaker_staff.id, female_staff.id}
    assert all(reminder.is_manual is False for reminder in reminders)
    assert response.data["candidate_id"] == candidate.id


def test_create_match_card_blocks_when_any_user_already_in_match(auth_client, matchmaker_staff, create_customer_profile, create_staff):
    female_staff = create_staff(name="女方红娘B")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        name="男方用户B",
        gender=CustomerProfile.GENDER_MALE,
        phone="13900139003",
        wechat="male_b_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        name="女方用户B",
        gender=CustomerProfile.GENDER_FEMALE,
        phone="13900139004",
        wechat="female_b_wx",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )

    client = auth_client(matchmaker_staff)
    _prepare_user_for_recommendation(male_user, matchmaker_staff)
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)
    male_user.is_in_match = True
    male_user.save(update_fields=["is_in_match"])

    response = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "USER_ALREADY_IN_MATCH"


def test_create_match_card_marks_candidate_met(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="女方红娘C")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
    )
    female_user = create_customer_profile(
        owner=other_staff,
        gender=CustomerProfile.GENDER_FEMALE,
    )

    client = auth_client(matchmaker_staff)
    _prepare_user_for_recommendation(male_user, matchmaker_staff)
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)

    response = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert response.status_code == 201
    candidate.refresh_from_db()
    assert candidate.is_met is True
    assert candidate.result == RecommendationCandidate.RESULT_CONTINUE


def test_create_match_card_blocks_reusing_processed_candidate(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="女方红娘C2")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
    )
    female_user = create_customer_profile(
        owner=other_staff,
        gender=CustomerProfile.GENDER_FEMALE,
    )

    client = auth_client(matchmaker_staff)
    _prepare_user_for_recommendation(male_user, matchmaker_staff)
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)

    first_resp = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )
    assert first_resp.status_code == 201

    male_user.refresh_from_db()
    female_user.refresh_from_db()
    male_user.is_in_match = False
    female_user.is_in_match = False
    male_user.save(update_fields=["is_in_match", "updated_at"])
    female_user.save(update_fields=["is_in_match", "updated_at"])

    second_resp = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert second_resp.status_code == 400
    assert second_resp.data["code"] == "CANDIDATE_ALREADY_PROCESSED"


def test_create_match_card_rejects_candidate_mismatch(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    other_staff = create_staff(name="女方红娘D")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
    )
    female_user = create_customer_profile(
        owner=other_staff,
        gender=CustomerProfile.GENDER_FEMALE,
    )
    wrong_male = create_customer_profile(
        owner=matchmaker_staff,
        gender=CustomerProfile.GENDER_MALE,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=False,
    )
    client = auth_client(matchmaker_staff)
    _prepare_user_for_recommendation(male_user, matchmaker_staff)
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)

    resp = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": wrong_male.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "CANDIDATE_MISMATCH"


def test_create_match_card_requires_selected_candidate(
    auth_client, matchmaker_staff, create_customer_profile, candidate_user
):
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        gender=CustomerProfile.GENDER_MALE,
        is_in_match=False,
    )
    female_user = candidate_user
    batch = RecommendationBatch.objects.create(
        user=male_user,
        staff=matchmaker_staff,
        batch_no="REC-SELECT-TEST",
        candidate_count=1,
        status=RecommendationBatch.STATUS_OPEN,
    )
    candidate = RecommendationCandidate.objects.create(batch=batch, candidate_user=female_user)

    client = auth_client(matchmaker_staff)
    resp = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_NOT_SELECTED"


def test_create_match_card_requires_existing_candidate(auth_client, matchmaker_staff, create_customer_profile, create_staff):
    other_staff = create_staff(name="女方红娘E")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
    )
    female_user = create_customer_profile(
        owner=other_staff,
        gender=CustomerProfile.GENDER_FEMALE,
    )
    client = auth_client(matchmaker_staff)

    resp = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": 999999,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["code"] == "CANDIDATE_NOT_FOUND"


def test_end_match_card_reflows_users_and_writes_history(
    auth_client, create_match_card, create_staff, matchmaker_staff
):
    female_staff = create_staff(name="女方红娘结束")
    card = create_match_card(
        male_staff=matchmaker_staff,
        female_staff=female_staff,
        primary_staff=matchmaker_staff,
    )
    male_user = card.male_user
    female_user = card.female_user
    old_male_last_action = male_user.last_action_at
    old_male_last_unmatched = male_user.last_unmatched_active_at
    old_female_last_action = female_user.last_action_at
    old_female_last_unmatched = female_user.last_unmatched_active_at

    response = auth_client(matchmaker_staff).post(
        f"/api/v1/match-cards/{card.id}/end/",
        {
            "end_reason_male": "节奏不合",
            "end_reason_female": "节奏不合",
            "end_reason_staff": "无共识",
        },
        format="json",
    )

    assert response.status_code == 200
    for user, old_action, old_unmatched in (
        (male_user, old_male_last_action, old_male_last_unmatched),
        (female_user, old_female_last_action, old_female_last_unmatched),
    ):
        user.refresh_from_db()
        assert user.pool_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
        assert user.last_action_at is not None
        assert user.last_unmatched_active_at is not None
        if old_action is not None:
            assert user.last_action_at > old_action
        if old_unmatched is not None:
            assert user.last_unmatched_active_at > old_unmatched
        assert "待重新推荐" in (user.tags or [])
        history = UserStatusHistory.objects.filter(user=user).order_by("-created_at").first()
        assert history.to_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
        assert history.reason == "配对卡结束自动回流"


def test_matchmaker_list_only_returns_involved_cards(auth_client, create_match_card, create_staff):
    viewer = create_staff(name="查看红娘")
    outsider = create_staff(name="无关红娘")
    create_match_card(male_staff=viewer)
    create_match_card(male_staff=outsider, female_staff=outsider, primary_staff=outsider)

    response = auth_client(viewer).get("/api/v1/match-cards/")

    assert response.status_code == 200
    assert response.data["count"] == 1


def test_admin_list_returns_all_cards(auth_client, admin_staff, create_match_card):
    create_match_card()
    create_match_card()

    response = auth_client(admin_staff).get("/api/v1/match-cards/")

    assert response.status_code == 200
    assert response.data["count"] == 2


def test_detail_requires_involved_staff_or_admin(auth_client, create_match_card, create_staff, admin_staff):
    involved_staff = create_staff(name="涉及红娘")
    outsider = create_staff(name="路人红娘")
    card = create_match_card(male_staff=involved_staff, primary_staff=involved_staff)

    involved_response = auth_client(involved_staff).get(f"/api/v1/match-cards/{card.id}/")
    admin_response = auth_client(admin_staff).get(f"/api/v1/match-cards/{card.id}/")
    outsider_response = auth_client(outsider).get(f"/api/v1/match-cards/{card.id}/")

    assert involved_response.status_code == 200
    assert admin_response.status_code == 200
    assert outsider_response.status_code == 403
    assert outsider_response.data["code"] == "PERMISSION_DENIED"


def test_male_staff_can_only_update_male_fields(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘C")
    female_staff = create_staff(name="女方红娘C")
    primary_staff = create_staff(name="主操作红娘C")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)

    ok_response = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "male_feedback": "男方反馈不错",
            "male_heat": 8,
        },
        format="json",
    )
    forbidden_response = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "female_feedback": "越权写女方反馈",
        },
        format="json",
    )

    assert ok_response.status_code == 200
    assert forbidden_response.status_code == 403
    assert forbidden_response.data["code"] == "PERMISSION_DENIED"


def test_female_staff_can_only_update_female_fields(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘D")
    female_staff = create_staff(name="女方红娘D")
    primary_staff = create_staff(name="主操作红娘D")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)

    ok_response = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "female_feedback": "女方反馈不错",
            "female_heat": 7,
        },
        format="json",
    )
    forbidden_response = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "male_feedback": "越权写男方反馈",
        },
        format="json",
    )

    assert ok_response.status_code == 200
    assert forbidden_response.status_code == 403
    assert forbidden_response.data["code"] == "PERMISSION_DENIED"


def test_primary_staff_and_admin_can_update_staff_judgment(auth_client, create_match_card, create_staff, admin_staff):
    male_staff = create_staff(name="男方红娘E")
    female_staff = create_staff(name="女方红娘E")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    primary_response = auth_client(male_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "主操作红娘判断关系稳定",
        },
        format="json",
    )
    admin_response = auth_client(admin_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "管理员补充判断",
        },
        format="json",
    )

    assert primary_response.status_code == 200
    assert admin_response.status_code == 200


def test_non_primary_staff_cannot_update_staff_judgment(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘F")
    female_staff = create_staff(name="女方红娘F")
    outsider = create_staff(name="无关红娘F")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    female_response = auth_client(female_staff).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "女方尝试越权",
        },
        format="json",
    )
    outsider_response = auth_client(outsider).patch(
        f"/api/v1/match-cards/{card.id}/",
        {
            "staff_judgment": "无关人员尝试越权",
        },
        format="json",
    )

    assert female_response.status_code == 403
    assert outsider_response.status_code == 403


def test_match_card_detail_returns_real_followups_and_valid_visit_count(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘详情")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.male_user,
        staff=primary_staff,
        content="男方反馈聊得不错",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.female_user,
        staff=primary_staff,
        content="女方反馈愿意继续",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_MANUAL,
        next_remind_at=timezone.now(),
    )

    response = auth_client(primary_staff).get(f"/api/v1/match-cards/{card.id}/")

    assert response.status_code == 200
    assert response.data["valid_visit_count"] == 2
    assert len(response.data["follow_ups"]) == 2
    assert response.data["follow_ups"][0]["staff_name"] == primary_staff.name


def test_create_match_card_rejects_when_neither_user_is_selected_pending_meet(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """BR-MATCH-001：男女双方均不处于 selected_pending_meet 时，建卡应被拦截。"""
    female_staff = create_staff(name="女方红娘neither")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        gender=CustomerProfile.GENDER_MALE,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )

    client = auth_client(matchmaker_staff)
    # 通过推荐流程拿到 candidate（select_candidate 会将 male_user 推进到 selected_pending_meet）
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)

    # 强制把 male_user 回退到 communicated_pending_recommend，使双方均不在 selected_pending_meet
    CustomerProfile.objects.filter(pk=male_user.pk).update(
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    )

    response = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "USER_STATUS_TRANSITION_INVALID"


def test_create_match_card_allows_when_only_initiating_user_is_selected_pending_meet(
    auth_client, matchmaker_staff, create_customer_profile, create_staff
):
    """BR-MATCH-001：只要"发起推荐的一方"处于 selected_pending_meet 即可建卡，
    候选方（对侧）的 pool_status 不做要求。

    此测试覆盖：男方（发起方）selected_pending_meet，女方（候选方）communicated_pending_recommend。
    """
    female_staff = create_staff(name="女方红娘atLeastOne")
    male_user = create_customer_profile(
        owner=matchmaker_staff,
        gender=CustomerProfile.GENDER_MALE,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
    )
    # female_user 保持 communicated_pending_recommend，不走推荐流程
    female_user = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
    )

    client = auth_client(matchmaker_staff)
    # select_candidate → male_user 进入 selected_pending_meet；female_user 状态不变
    candidate = _select_recommendation_candidate(client, male_user, female_user.id)

    female_user.refresh_from_db()
    male_user.refresh_from_db()
    # 确认测试前置条件
    assert male_user.pool_status == CustomerProfile.STATUS_SELECTED_PENDING_MEET
    assert female_user.pool_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND

    response = client.post(
        "/api/v1/match-cards/",
        {
            "male_user_id": male_user.id,
            "female_user_id": female_user.id,
            "candidate_id": candidate.id,
        },
        format="json",
    )

    assert response.status_code == 201
