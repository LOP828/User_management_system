import pytest
from datetime import timedelta
from rest_framework import status
from uuid import uuid4
from django.utils import timezone

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


@pytest.fixture
def create_match_card(create_customer_profile, create_staff):
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


def test_non_primary_staff_cannot_advance_stage(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘A")
    female_staff = create_staff(name="女方红娘A")
    primary_staff = create_staff(name="主操作红娘A")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)

    response = auth_client(male_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_STABLE_CONTACT, "reason": "尝试推进"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_advance_stage_blocks_invalid_transition(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘B")
    card = create_match_card(primary_staff=primary_staff)

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_SUCCESS_PENDING_REVIEW},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "MATCH_STAGE_TRANSITION_INVALID"


def test_advance_stage_requires_visits_for_initial_to_stable(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘C")
    card = create_match_card(primary_staff=primary_staff, stage=MatchCard.STAGE_INITIAL_CONTACT)

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_STABLE_CONTACT},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "MATCH_NOT_ENOUGH_VISITS"


def test_advance_stage_allows_initial_to_stable_with_one_valid_visit_per_side(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘C1")
    female_staff = create_staff(name="女方红娘C1")
    card = create_match_card(
        primary_staff=primary_staff,
        male_staff=primary_staff,
        female_staff=female_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.male_user,
        staff=primary_staff,
        content="男方第一次有效回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.female_user,
        staff=female_staff,
        content="女方第一次有效回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_STABLE_CONTACT, "reason": "双方均有有效回访"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stage"] == MatchCard.STAGE_STABLE_CONTACT
    card.refresh_from_db()
    assert card.stage == MatchCard.STAGE_STABLE_CONTACT


def test_advance_stage_does_not_count_invalid_followups_for_initial_to_stable(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘C2")
    female_staff = create_staff(name="女方红娘C2")
    card = create_match_card(
        primary_staff=primary_staff,
        male_staff=primary_staff,
        female_staff=female_staff,
        stage=MatchCard.STAGE_INITIAL_CONTACT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.male_user,
        staff=primary_staff,
        content="男方有效回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.female_user,
        staff=female_staff,
        content="女方无效回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_MANUAL,
        next_remind_at=None,
    )

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_STABLE_CONTACT},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "MATCH_NOT_ENOUGH_VISITS"


def test_advance_stage_requires_duration_for_stable_to_success_pending(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘D")
    card = create_match_card(primary_staff=primary_staff, stage=MatchCard.STAGE_STABLE_CONTACT)

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_SUCCESS_PENDING_REVIEW},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "MATCH_DURATION_TOO_SHORT"


def test_advance_stage_requires_two_valid_visits_per_side_for_stable_to_success_pending(
    auth_client,
    create_match_card,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘D1")
    female_staff = create_staff(name="女方红娘D1")
    card = create_match_card(
        primary_staff=primary_staff,
        male_staff=primary_staff,
        female_staff=female_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()

    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.male_user,
        staff=primary_staff,
        content="男方第一次有效回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )
    FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_MATCHED,
        match_card=card,
        user=card.female_user,
        staff=female_staff,
        content="女方第一次有效回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=FollowUpRecord.RISK_NONE,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_SUCCESS_PENDING_REVIEW},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "MATCH_NOT_ENOUGH_VISITS"


def test_advance_stage_allows_stable_to_success_pending_with_real_valid_visits_and_duration(
    auth_client,
    create_match_card,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘D2")
    female_staff = create_staff(name="女方红娘D2")
    card = create_match_card(
        primary_staff=primary_staff,
        male_staff=primary_staff,
        female_staff=female_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
    )
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()

    for content, user, staff in [
        ("男方第一次有效回访", card.male_user, primary_staff),
        ("男方第二次有效回访", card.male_user, primary_staff),
        ("女方第一次有效回访", card.female_user, female_staff),
        ("女方第二次有效回访", card.female_user, female_staff),
    ]:
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_MATCHED,
            match_card=card,
            user=user,
            staff=staff,
            content=content,
            is_still_contact=FollowUpRecord.CONTACT_YES,
            risk_status=FollowUpRecord.RISK_NONE,
            next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
        )

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/advance-stage/",
        {"to_stage": MatchCard.STAGE_SUCCESS_PENDING_REVIEW, "reason": "满足回访与时长条件"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stage"] == MatchCard.STAGE_SUCCESS_PENDING_REVIEW
    card.refresh_from_db()
    assert card.stage == MatchCard.STAGE_SUCCESS_PENDING_REVIEW


def test_set_risk_requires_reason_for_watching(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘E")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)

    response = auth_client(male_staff).post(
        f"/api/v1/match-cards/{card.id}/set-risk/",
        {"risk_level": MatchCard.RISK_WATCHING},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "RISK_REASON_REQUIRED"


def test_set_risk_none_clears_reason_fields(auth_client, create_match_card, create_staff, create_reason_enum):
    male_staff = create_staff(name="男方红娘F")
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_RISK, label="沟通冲突", sort_order=1)
    card = create_match_card(
        male_staff=male_staff,
        primary_staff=male_staff,
        risk_level=MatchCard.RISK_WATCHING,
        risk_reason=reason,
        risk_reason_note="已有风险备注",
    )

    response = auth_client(male_staff).post(
        f"/api/v1/match-cards/{card.id}/set-risk/",
        {"risk_level": MatchCard.RISK_NONE},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    card.refresh_from_db()
    assert card.risk_level == MatchCard.RISK_NONE
    assert card.risk_reason is None
    assert card.risk_reason_note is None


def test_outsider_cannot_set_risk(auth_client, create_match_card, create_staff, create_reason_enum):
    involved = create_staff(name="涉及红娘")
    outsider = create_staff(name="无关红娘")
    reason = create_reason_enum(category=ReasonEnum.CATEGORY_RISK, label="节奏不一致", sort_order=2)
    card = create_match_card(male_staff=involved, primary_staff=involved)

    response = auth_client(outsider).post(
        f"/api/v1/match-cards/{card.id}/set-risk/",
        {
            "risk_level": MatchCard.RISK_WATCHING,
            "risk_reason_id": reason.id,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_end_requires_staff_reason(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘G")
    card = create_match_card(primary_staff=primary_staff, stage=MatchCard.STAGE_STABLE_CONTACT)

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/end/",
        {"end_reason_male": "男方原因"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "END_REASON_REQUIRED"


def test_non_primary_staff_cannot_end(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘H")
    primary_staff = create_staff(name="主操作红娘H")
    card = create_match_card(male_staff=male_staff, primary_staff=primary_staff, stage=MatchCard.STAGE_STABLE_CONTACT)

    response = auth_client(male_staff).post(
        f"/api/v1/match-cards/{card.id}/end/",
        {"end_reason_staff": "尝试结束"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["code"] == "PERMISSION_DENIED"


def test_end_reflows_users_and_appends_emotional_history(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘I")
    card = create_match_card(primary_staff=primary_staff, stage=MatchCard.STAGE_STABLE_CONTACT)

    response = auth_client(primary_staff).post(
        f"/api/v1/match-cards/{card.id}/end/",
        {
            "end_reason_male": "男方觉得节奏太快",
            "end_reason_female": "女方暂不考虑",
            "end_reason_staff": "双方节奏不一致，决定结束",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["stage"] == MatchCard.STAGE_ENDED
    assert len(response.data["reflowed_users"]) == 2

    card.refresh_from_db()
    card.male_user.refresh_from_db()
    card.female_user.refresh_from_db()
    assert card.ended_at is not None
    assert card.next_remind_at is None
    assert card.male_user.is_in_match is False
    assert card.female_user.is_in_match is False
    assert card.male_user.pool_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert card.female_user.pool_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert "待重新推荐" in (card.male_user.tags or [])
    assert "待重新推荐" in (card.female_user.tags or [])
    assert len(card.male_user.emotional_history or []) == 1
    assert len(card.female_user.emotional_history or []) == 1
