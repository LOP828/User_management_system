from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.success.models import SuccessApplication, SuccessCase
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


@pytest.fixture
def create_follow_up(create_match_card, create_staff):
    def factory(**kwargs):
        match_card = kwargs.pop("match_card") if "match_card" in kwargs else create_match_card()
        staff = kwargs.pop("staff", None) or (match_card.primary_staff if match_card is not None else create_staff(name="跟进红娘"))
        user = kwargs.pop("user") if "user" in kwargs else match_card.male_user
        defaults = {
            "scene": FollowUpRecord.SCENE_MATCHED,
            "match_card": match_card,
            "user": user,
            "staff": staff,
            "content": "回访记录",
            "is_still_contact": FollowUpRecord.CONTACT_YES,
            "risk_status": FollowUpRecord.RISK_NONE,
            "next_remind_mode": FollowUpRecord.REMIND_DEFAULT,
            "next_remind_at": None,
        }
        defaults.update(kwargs)
        return FollowUpRecord.objects.create(**defaults)

    return factory


@pytest.fixture
def create_success_application(create_match_card, create_staff):
    def factory(**kwargs):
        match_card = kwargs.pop("match_card", None) or create_match_card(stage=MatchCard.STAGE_SUCCESS)
        applicant = kwargs.pop("applicant", None) or match_card.primary_staff
        defaults = {
            "match_card": match_card,
            "applicant": applicant,
            "apply_note": "双方关系稳定，申请成功",
            "status": SuccessApplication.STATUS_APPROVED,
        }
        defaults.update(kwargs)
        return SuccessApplication.objects.create(**defaults)

    return factory


@pytest.fixture
def create_success_case(create_success_application):
    def factory(**kwargs):
        application = kwargs.pop("application", None)
        match_card = kwargs.pop("match_card", None)
        if application is None:
            application = create_success_application(match_card=match_card)
        if match_card is None:
            match_card = application.match_card
        defaults = {
            "match_card": match_card,
            "application": application,
            "status": SuccessCase.STATUS_ACTIVE,
            "approved_at": timezone.now(),
        }
        defaults.update(kwargs)
        success_case = SuccessCase.objects.create(**defaults)
        match_card.stage = MatchCard.STAGE_SUCCESS
        match_card.next_remind_at = None
        match_card.save(update_fields=["stage", "next_remind_at", "updated_at"])
        match_card.male_user.is_in_match = False
        match_card.male_user.save(update_fields=["is_in_match", "updated_at"])
        match_card.female_user.is_in_match = False
        match_card.female_user.save(update_fields=["is_in_match", "updated_at"])
        return success_case

    return factory


def test_create_followup_updates_match_card_last_visit_and_returns_valid_visit(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘A")
    female_staff = create_staff(name="女方红娘A")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)

    response = auth_client(male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "男方反馈愿意继续接触",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "manual",
            "next_remind_at": "2026-03-20T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["scene"] == "matched"
    assert response.data["is_valid_visit"] is True
    assert response.data["staff_id"] == male_staff.id

    card.refresh_from_db()
    card.male_user.refresh_from_db()
    assert card.last_visit_at is not None
    assert card.male_user.last_action_at is not None
    assert card.next_remind_at == follow_up_time("2026-03-20T09:00:00Z")


def follow_up_time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def test_create_followup_default_mode_updates_match_card_next_remind_at(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘A1")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)

    response = auth_client(male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "男方第一次有效回访",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 201
    card.refresh_from_db()
    assert card.next_remind_at == card.created_at + timedelta(days=14)


def test_create_followup_requires_matched_fields(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘B")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)

    response = auth_client(male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "只填内容",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "is_still_contact" in response.data["details"]
    assert "risk_status" in response.data["details"]
    assert "next_remind_mode" in response.data["details"]


def test_create_followup_rejects_default_with_next_remind_at(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘C")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)

    response = auth_client(male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "男方反馈状态稳定",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "default",
            "next_remind_at": "2026-03-20T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "next_remind_at" in response.data["details"]


def test_owner_can_create_unmatched_followup(auth_client, create_customer_profile, matchmaker_staff):
    user = create_customer_profile(owner=matchmaker_staff)

    response = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "unmatched",
            "user_id": user.id,
            "content": "未配对跟进",
            "next_remind_at": "2026-03-16T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["scene"] == "unmatched"
    assert response.data["user_id"] == user.id
    assert response.data["match_card_id"] is None
    assert response.data["next_remind_mode"] == "manual"
    assert response.data["is_valid_visit"] is False

    user.refresh_from_db()
    assert user.last_action_at is not None
    assert user.last_unmatched_active_at is not None


def test_unmatched_followup_supports_failure_reason(auth_client, create_customer_profile, create_reason_enum, matchmaker_staff):
    user = create_customer_profile(owner=matchmaker_staff)
    failure_reason = create_reason_enum(category="meet_failure", label="性格不合")

    response = auth_client(matchmaker_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "unmatched",
            "user_id": user.id,
            "content": "首次见面后，双方觉得不合适",
            "failure_reason_id": failure_reason.id,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["failure_reason_id"] == failure_reason.id


def test_non_owner_cannot_create_unmatched_followup(auth_client, create_customer_profile, create_staff):
    owner = create_staff(name="负责人U1")
    outsider = create_staff(name="无关红娘U1")
    user = create_customer_profile(owner=owner)

    response = auth_client(outsider).post(
        "/api/v1/follow-ups/",
        {
            "scene": "unmatched",
            "user_id": user.id,
            "content": "越权写未配对跟进",
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_unmatched_followup_rejects_match_card_and_default_mode(
    auth_client,
    create_customer_profile,
    create_match_card,
    create_staff,
):
    owner = create_staff(name="负责人U2")
    user = create_customer_profile(owner=owner)
    match_card = create_match_card(primary_staff=owner, male_staff=owner)

    response = auth_client(owner).post(
        "/api/v1/follow-ups/",
        {
            "scene": "unmatched",
            "user_id": user.id,
            "match_card_id": match_card.id,
            "content": "错误传了配对卡",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "match_card_id" in response.data["details"] or "next_remind_mode" in response.data["details"]


def test_primary_staff_can_create_success_followup(auth_client, create_match_card, create_success_case, create_staff):
    primary_staff = create_staff(name="主操作红娘S1")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_SUCCESS)
    create_success_case(match_card=card)

    response = auth_client(primary_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "content": "双方仍在交往中，感情稳定",
            "is_still_contact": "yes",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["scene"] == "success_followup"
    assert response.data["user_id"] is None
    assert response.data["is_valid_visit"] is True

    card.male_user.refresh_from_db()
    card.female_user.refresh_from_db()
    assert card.male_user.last_action_at is not None
    assert card.female_user.last_action_at is not None


def test_success_followup_requires_success_stage(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘S2")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_STABLE_CONTACT)

    response = auth_client(primary_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "content": "尝试提前写成功后回访",
            "is_still_contact": "yes",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "MATCH_STAGE_TRANSITION_INVALID"


def test_success_followup_requires_minimum_fields(auth_client, create_match_card, create_success_case, create_staff):
    primary_staff = create_staff(name="主操作红娘S3")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_SUCCESS)
    create_success_case(match_card=card)

    response = auth_client(primary_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "content": "只填内容",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "is_still_contact" in response.data["details"]
    assert "next_remind_mode" in response.data["details"]
    assert "risk_status" not in response.data["details"]


def test_success_followup_rejects_user_id(auth_client, create_match_card, create_success_case, create_staff):
    primary_staff = create_staff(name="主操作红娘S4")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_SUCCESS)
    create_success_case(match_card=card)

    response = auth_client(primary_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "user_id": card.male_user_id,
            "content": "错误传了 user_id",
            "is_still_contact": "yes",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "user_id" in response.data["details"]


def test_non_primary_staff_cannot_create_success_followup(
    auth_client,
    create_match_card,
    create_success_case,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘S5")
    female_staff = create_staff(name="女方红娘S5")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, female_staff=female_staff, stage=MatchCard.STAGE_SUCCESS)
    create_success_case(match_card=card)

    response = auth_client(female_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "success_followup",
            "match_card_id": card.id,
            "content": "越权写成功后回访",
            "is_still_contact": "yes",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_primary_staff_can_patch_success_followup(
    auth_client,
    create_match_card,
    create_success_case,
    create_follow_up,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘S6")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_SUCCESS)
    create_success_case(match_card=card)
    follow_up = create_follow_up(
        scene=FollowUpRecord.SCENE_SUCCESS_FOLLOWUP,
        match_card=card,
        staff=primary_staff,
        user=None,
        content="首次成功后回访",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        risk_status=None,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
        next_remind_at=None,
    )

    response = auth_client(primary_staff).patch(
        f"/api/v1/follow-ups/{follow_up.id}/",
        {
            "content": "双方仍在一起，状态稳定",
            "next_remind_mode": "manual",
            "next_remind_at": "2026-04-01T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 200
    follow_up.refresh_from_db()
    assert follow_up.content == "双方仍在一起，状态稳定"
    assert follow_up.next_remind_mode == FollowUpRecord.REMIND_MANUAL
    assert follow_up.next_remind_at == follow_up_time("2026-04-01T09:00:00Z")


def test_male_staff_cannot_create_female_side_followup(auth_client, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘D")
    female_staff = create_staff(name="女方红娘D")
    primary_staff = create_staff(name="主操作红娘D")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)

    response = auth_client(male_staff).post(
        "/api/v1/follow-ups/",
        {
            "scene": "matched",
            "match_card_id": card.id,
            "user_id": card.female_user_id,
            "content": "越权写女方侧回访",
            "is_still_contact": "yes",
            "risk_status": "none",
            "next_remind_mode": "default",
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_related_staff_can_list_followups(auth_client, create_follow_up, create_match_card, create_staff):
    viewer = create_staff(name="查看红娘")
    outsider = create_staff(name="无关红娘")
    related_card = create_match_card(male_staff=viewer, primary_staff=viewer)
    outsider_card = create_match_card(male_staff=outsider, female_staff=outsider, primary_staff=outsider)
    create_follow_up(match_card=related_card, user=related_card.male_user, staff=viewer)
    create_follow_up(match_card=outsider_card, user=outsider_card.male_user, staff=outsider)

    response = auth_client(viewer).get("/api/v1/follow-ups/")

    assert response.status_code == 200
    assert response.data["count"] == 1


def test_owner_can_list_unmatched_followups(auth_client, create_customer_profile, create_follow_up, create_staff):
    owner = create_staff(name="负责人U3")
    outsider = create_staff(name="无关红娘U3")
    own_user = create_customer_profile(owner=owner)
    other_user = create_customer_profile(owner=outsider, phone="13900139001", wechat="other_user_u3")
    own_follow_up = create_follow_up(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        match_card=None,
        user=own_user,
        staff=owner,
        content="电话回访，补充择偶要求",
        is_still_contact=None,
        risk_status=None,
        next_remind_mode=None,
        next_remind_at=None,
    )
    create_follow_up(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        match_card=None,
        user=other_user,
        staff=outsider,
        content="无关未配对跟进",
        is_still_contact=None,
        risk_status=None,
        next_remind_mode=None,
        next_remind_at=None,
    )

    response = auth_client(owner).get("/api/v1/follow-ups/?scene=unmatched")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == own_follow_up.id


def test_outsider_cannot_get_followup_detail(auth_client, create_follow_up, create_staff):
    involved = create_staff(name="涉及红娘")
    outsider = create_staff(name="无关红娘")
    follow_up = create_follow_up(staff=involved)

    response = auth_client(outsider).get(f"/api/v1/follow-ups/{follow_up.id}/")

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_owner_can_get_unmatched_followup_detail(auth_client, create_customer_profile, create_follow_up, create_staff):
    owner = create_staff(name="负责人U4")
    user = create_customer_profile(owner=owner)
    follow_up = create_follow_up(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        match_card=None,
        user=user,
        staff=owner,
        content="未配对阶段再次电话跟进",
        is_still_contact=None,
        risk_status=None,
        next_remind_mode=None,
        next_remind_at=None,
    )

    response = auth_client(owner).get(f"/api/v1/follow-ups/{follow_up.id}/")

    assert response.status_code == 200
    assert response.data["id"] == follow_up.id
    assert response.data["scene"] == "unmatched"
    assert response.data["user_id"] == user.id


def test_followup_detail_visible_to_related_staff(auth_client, create_follow_up, create_staff):
    male_staff = create_staff(name="男方红娘E")
    card_follow_up = create_follow_up(staff=male_staff)

    response = auth_client(male_staff).get(f"/api/v1/follow-ups/{card_follow_up.id}/")

    assert response.status_code == 200
    assert response.data["id"] == card_follow_up.id
    assert response.data["staff_id"] == male_staff.id


def test_side_staff_can_patch_followup(auth_client, create_follow_up, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘F")
    card = create_match_card(male_staff=male_staff, primary_staff=male_staff)
    follow_up = create_follow_up(match_card=card, user=card.male_user, staff=male_staff)

    response = auth_client(male_staff).patch(
        f"/api/v1/follow-ups/{follow_up.id}/",
        {
            "content": "男方确认愿意继续推进",
            "next_remind_mode": "manual",
            "next_remind_at": "2026-03-22T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 200
    follow_up.refresh_from_db()
    card.refresh_from_db()
    assert follow_up.content == "男方确认愿意继续推进"
    assert follow_up.next_remind_mode == FollowUpRecord.REMIND_MANUAL
    assert card.next_remind_at == follow_up_time("2026-03-22T09:00:00Z")


def test_owner_can_patch_unmatched_followup(auth_client, create_customer_profile, create_follow_up, create_staff):
    owner = create_staff(name="负责人U5")
    user = create_customer_profile(owner=owner)
    follow_up = create_follow_up(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        match_card=None,
        user=user,
        staff=owner,
        content="首次未配对跟进",
        is_still_contact=None,
        risk_status=None,
        next_remind_mode=None,
        next_remind_at=None,
    )

    response = auth_client(owner).patch(
        f"/api/v1/follow-ups/{follow_up.id}/",
        {
            "content": "更新沟通结果，准备再次联系",
            "next_remind_at": "2026-03-25T09:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 200
    follow_up.refresh_from_db()
    user.refresh_from_db()
    assert follow_up.content == "更新沟通结果，准备再次联系"
    assert follow_up.next_remind_mode == FollowUpRecord.REMIND_MANUAL
    assert follow_up.next_remind_at == follow_up_time("2026-03-25T09:00:00Z")
    assert user.last_action_at is not None
    assert user.last_unmatched_active_at is not None


def test_non_side_staff_cannot_patch_followup(auth_client, create_follow_up, create_match_card, create_staff):
    male_staff = create_staff(name="男方红娘G")
    female_staff = create_staff(name="女方红娘G")
    primary_staff = create_staff(name="主操作红娘G")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=primary_staff)
    follow_up = create_follow_up(match_card=card, user=card.male_user, staff=male_staff)

    outsider = create_staff(name="无关红娘G")
    response = auth_client(outsider).patch(
        f"/api/v1/follow-ups/{follow_up.id}/",
        {"content": "越权编辑"},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_non_owner_cannot_patch_unmatched_followup(auth_client, create_customer_profile, create_follow_up, create_staff):
    owner = create_staff(name="负责人U6")
    outsider = create_staff(name="无关红娘U6")
    user = create_customer_profile(owner=owner)
    follow_up = create_follow_up(
        scene=FollowUpRecord.SCENE_UNMATCHED,
        match_card=None,
        user=user,
        staff=owner,
        content="未配对初次跟进",
        is_still_contact=None,
        risk_status=None,
        next_remind_mode=None,
        next_remind_at=None,
    )

    response = auth_client(outsider).patch(
        f"/api/v1/follow-ups/{follow_up.id}/",
        {"content": "越权编辑未配对跟进"},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_patch_rejects_forbidden_fields(auth_client, create_follow_up, create_staff):
    male_staff = create_staff(name="男方红娘H")
    follow_up = create_follow_up(staff=male_staff)

    response = auth_client(male_staff).patch(
        f"/api/v1/follow-ups/{follow_up.id}/",
        {"user_id": follow_up.match_card.female_user_id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
