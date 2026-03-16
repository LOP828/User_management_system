from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.oplog.models import OperationLog
from apps.success.models import SuccessApplication, SuccessCase
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


def seed_success_application_prerequisites(match_card, *, male_count=2, female_count=2, staff_judgment="主操作红娘确认双方已建立恋爱关系"):
    for index in range(male_count):
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_MATCHED,
            match_card=match_card,
            user=match_card.male_user,
            staff=match_card.male_staff,
            content=f"男方有效回访{index + 1}",
            is_still_contact=FollowUpRecord.CONTACT_YES,
            risk_status=FollowUpRecord.RISK_NONE,
            next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
        )
    for index in range(female_count):
        FollowUpRecord.objects.create(
            scene=FollowUpRecord.SCENE_MATCHED,
            match_card=match_card,
            user=match_card.female_user,
            staff=match_card.female_staff,
            content=f"女方有效回访{index + 1}",
            is_still_contact=FollowUpRecord.CONTACT_YES,
            risk_status=FollowUpRecord.RISK_NONE,
            next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
        )
    if staff_judgment is not None:
        match_card.staff_judgment = staff_judgment
        match_card.save(update_fields=["staff_judgment", "updated_at"])


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
            "stage": MatchCard.STAGE_STABLE_CONTACT,
            "risk_level": MatchCard.RISK_NONE,
        }
        defaults.update(kwargs)
        return MatchCard.objects.create(**defaults)

    return factory


@pytest.fixture
def create_success_application(create_match_card, create_staff):
    def factory(**kwargs):
        match_card = kwargs.pop("match_card", None) or create_match_card()
        applicant = kwargs.pop("applicant", None) or match_card.primary_staff
        defaults = {
            "match_card": match_card,
            "applicant": applicant,
            "apply_note": "双方关系稳定，申请成功",
            "status": SuccessApplication.STATUS_PENDING,
        }
        defaults.update(kwargs)
        app = SuccessApplication.objects.create(**defaults)
        # Mimic service: advance stage to success_pending_review
        if match_card.stage == MatchCard.STAGE_STABLE_CONTACT:
            match_card.stage = MatchCard.STAGE_SUCCESS_PENDING_REVIEW
            match_card.save(update_fields=["stage", "updated_at"])
        return app

    return factory


@pytest.fixture
def create_success_case(create_success_application):
    def factory(**kwargs):
        application = kwargs.pop("application", None)
        match_card = kwargs.pop("match_card", None)
        if application is None:
            application = create_success_application(
                match_card=match_card,
                status=SuccessApplication.STATUS_APPROVED,
            )
        if match_card is None:
            match_card = application.match_card
        approved_at = kwargs.pop("approved_at", timezone.now())
        defaults = {
            "match_card": match_card,
            "application": application,
            "status": SuccessCase.STATUS_ACTIVE,
            "approved_at": approved_at,
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


def test_primary_staff_can_create_success_application(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘A")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    seed_success_application_prerequisites(card)

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {
            "match_card_id": card.id,
            "apply_note": "双方交往稳定，申请进入成功审批",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["match_card_id"] == card.id
    assert response.data["status"] == SuccessApplication.STATUS_PENDING
    assert response.data["applicant_id"] == primary_staff.id


def test_success_application_transitions_card_to_success_pending_review(auth_client, create_match_card, create_staff):
    """BR-SUCCESS-001 + PRD §16.2: 创建成功申请后，配对卡 stage 自动推进到 success_pending_review。"""
    primary_staff = create_staff(name="主操作红娘A2")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    assert card.stage == MatchCard.STAGE_STABLE_CONTACT
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    seed_success_application_prerequisites(card)

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id, "apply_note": "双方交往稳定"},
        format="json",
    )

    assert response.status_code == 201
    card.refresh_from_db()
    assert card.stage == MatchCard.STAGE_SUCCESS_PENDING_REVIEW


def test_success_application_requires_stable_contact_stage(auth_client, create_match_card, create_staff):
    """BR-SUCCESS-001: 只能从 stable_contact 发起成功申请，其他阶段被拒。"""
    primary_staff = create_staff(name="主操作红娘B")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, stage=MatchCard.STAGE_INITIAL_CONTACT)
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "MATCH_STAGE_TRANSITION_INVALID"


def test_success_application_requires_duration(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘C")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    seed_success_application_prerequisites(card)

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "MATCH_DURATION_TOO_SHORT"


def test_success_application_requires_two_valid_visits_per_side(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘C1")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    seed_success_application_prerequisites(card, male_count=1, female_count=2)

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "MATCH_NOT_ENOUGH_VISITS"


def test_success_application_requires_relationship_confirmation(auth_client, create_match_card, create_staff):
    primary_staff = create_staff(name="主操作红娘C2")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    seed_success_application_prerequisites(card, staff_judgment=None)

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "MATCH_RELATIONSHIP_NOT_CONFIRMED"


def test_success_application_blocks_duplicate_pending(auth_client, create_match_card, create_success_application, create_staff):
    primary_staff = create_staff(name="主操作红娘D")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    seed_success_application_prerequisites(card)
    create_success_application(match_card=card, applicant=primary_staff)

    # fixture 已将 stage 推到 success_pending_review，回退到 stable_contact 以通过阶段检查，
    # 验证即使阶段合法也会被"已有 pending 申请"拦截
    card.stage = MatchCard.STAGE_STABLE_CONTACT
    card.save(update_fields=["stage", "updated_at"])

    response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "SUCCESS_PENDING_EXISTS"


def test_admin_can_approve_success_application(auth_client, admin_staff, create_match_card, create_success_application, create_staff):
    primary_staff = create_staff(name="主操作红娘E")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    application = create_success_application(match_card=card, applicant=primary_staff)

    response = auth_client(admin_staff).post(
        f"/api/v1/success-applications/{application.id}/approve/",
        {},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == SuccessApplication.STATUS_APPROVED
    assert "success_case_id" in response.data

    application.refresh_from_db()
    card.refresh_from_db()
    card.male_user.refresh_from_db()
    card.female_user.refresh_from_db()
    success_case = SuccessCase.objects.get(application=application)
    assert application.status == SuccessApplication.STATUS_APPROVED
    assert card.stage == MatchCard.STAGE_SUCCESS
    assert success_case.status == SuccessCase.STATUS_ACTIVE
    assert card.male_user.is_in_match is False
    assert card.female_user.is_in_match is False
    assert card.next_remind_at is None


def test_matchmaker_cannot_approve_success_application(auth_client, create_success_application, create_staff):
    primary_staff = create_staff(name="主操作红娘F")
    application = create_success_application(applicant=primary_staff)

    response = auth_client(primary_staff).post(
        f"/api/v1/success-applications/{application.id}/approve/",
        {},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_admin_reject_requires_review_note(auth_client, admin_staff, create_success_application):
    application = create_success_application()

    response = auth_client(admin_staff).post(
        f"/api/v1/success-applications/{application.id}/reject/",
        {},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "review_note" in response.data["details"]


def test_admin_can_reject_success_application_and_reapply(auth_client, admin_staff, create_match_card, create_success_application, create_staff):
    primary_staff = create_staff(name="主操作红娘G")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    seed_success_application_prerequisites(card)
    application = create_success_application(match_card=card, applicant=primary_staff)

    reject_response = auth_client(admin_staff).post(
        f"/api/v1/success-applications/{application.id}/reject/",
        {"review_note": "观察期还不够，先回退稳定联系"},
        format="json",
    )

    assert reject_response.status_code == 200
    application.refresh_from_db()
    card.refresh_from_db()
    assert application.status == SuccessApplication.STATUS_REJECTED
    assert card.stage == MatchCard.STAGE_STABLE_CONTACT

    # 驳回后 stage 已回退到 stable_contact，可直接重新申请（无需手动设置 stage）
    reapply_response = auth_client(primary_staff).post(
        "/api/v1/success-applications/",
        {"match_card_id": card.id, "apply_note": "补充观察后再次申请"},
        format="json",
    )

    assert reapply_response.status_code == 201


def test_success_application_list_scope_admin_and_matchmaker(auth_client, admin_staff, create_success_application, create_staff):
    owner = create_staff(name="申请红娘H")
    other = create_staff(name="其他红娘H")
    own_application = create_success_application(applicant=owner)
    create_success_application(applicant=other)

    owner_response = auth_client(owner).get("/api/v1/success-applications/")
    admin_response = auth_client(admin_staff).get("/api/v1/success-applications/")

    assert owner_response.status_code == 200
    assert owner_response.data["count"] == 1
    assert owner_response.data["results"][0]["id"] == own_application.id
    assert admin_response.status_code == 200
    assert admin_response.data["count"] == 2


def test_success_case_list_scope_admin_and_related_staff(
    auth_client,
    admin_staff,
    create_match_card,
    create_success_application,
    create_success_case,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘I")
    related_card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    related_application = create_success_application(match_card=related_card, applicant=primary_staff, status=SuccessApplication.STATUS_APPROVED)
    related_case = create_success_case(match_card=related_card, application=related_application)

    other_staff = create_staff(name="其他红娘I")
    other_card = create_match_card(primary_staff=other_staff, male_staff=other_staff)
    other_application = create_success_application(match_card=other_card, applicant=other_staff, status=SuccessApplication.STATUS_APPROVED)
    create_success_case(match_card=other_card, application=other_application)

    owner_response = auth_client(primary_staff).get("/api/v1/success-cases/")
    admin_response = auth_client(admin_staff).get("/api/v1/success-cases/")

    assert owner_response.status_code == 200
    assert owner_response.data["count"] == 1
    assert owner_response.data["results"][0]["id"] == related_case.id
    assert admin_response.status_code == 200
    assert admin_response.data["count"] == 2


def test_related_staff_can_view_success_case_detail(auth_client, create_match_card, create_success_application, create_success_case, create_staff):
    male_staff = create_staff(name="男方红娘J")
    female_staff = create_staff(name="女方红娘J")
    card = create_match_card(male_staff=male_staff, female_staff=female_staff, primary_staff=male_staff)
    application = create_success_application(match_card=card, applicant=male_staff, status=SuccessApplication.STATUS_APPROVED)
    success_case = create_success_case(match_card=card, application=application)

    response = auth_client(female_staff).get(f"/api/v1/success-cases/{success_case.id}/")

    assert response.status_code == 200
    assert response.data["id"] == success_case.id
    assert response.data["match_card_id"] == card.id
    assert response.data["match_card_stage"] == MatchCard.STAGE_SUCCESS
    assert response.data["female_user_id"] == card.female_user_id


def test_success_case_detail_returns_success_followups(
    auth_client,
    create_match_card,
    create_success_application,
    create_success_case,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘J1")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    application = create_success_application(match_card=card, applicant=primary_staff, status=SuccessApplication.STATUS_APPROVED)
    success_case = create_success_case(match_card=card, application=application)
    older_follow_up = FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_SUCCESS_FOLLOWUP,
        match_card=card,
        user=None,
        staff=primary_staff,
        content="双方相处稳定",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        next_remind_mode=FollowUpRecord.REMIND_DEFAULT,
    )
    newer_follow_up = FollowUpRecord.objects.create(
        scene=FollowUpRecord.SCENE_SUCCESS_FOLLOWUP,
        match_card=card,
        user=None,
        staff=primary_staff,
        content="最近准备见家长",
        is_still_contact=FollowUpRecord.CONTACT_YES,
        next_remind_mode=FollowUpRecord.REMIND_MANUAL,
        next_remind_at=timezone.now() + timedelta(days=30),
    )

    response = auth_client(primary_staff).get(f"/api/v1/success-cases/{success_case.id}/")

    assert response.status_code == 200
    assert len(response.data["follow_ups"]) == 2
    assert response.data["follow_ups"][0]["id"] == newer_follow_up.id
    assert response.data["follow_ups"][1]["id"] == older_follow_up.id
    assert response.data["follow_ups"][0]["is_valid_visit"] is True


def test_unrelated_matchmaker_cannot_view_success_case_detail(
    auth_client,
    create_success_case,
    create_staff,
):
    success_case = create_success_case()
    outsider = create_staff(name="无关红娘K")

    response = auth_client(outsider).get(f"/api/v1/success-cases/{success_case.id}/")

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_primary_staff_can_invalidate_success_case_and_write_operation_log(
    auth_client,
    create_match_card,
    create_success_application,
    create_success_case,
    create_reason_enum,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘L")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff)
    application = create_success_application(match_card=card, applicant=primary_staff, status=SuccessApplication.STATUS_APPROVED)
    success_case = create_success_case(match_card=card, application=application)
    invalidate_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
        label="双方已分手",
    )
    male_pool_status = card.male_user.pool_status
    female_pool_status = card.female_user.pool_status

    response = auth_client(primary_staff).post(
        f"/api/v1/success-cases/{success_case.id}/invalidate/",
        {
            "reason_id": invalidate_reason.id,
            "reason_note": "关系结束，标记成功失效",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["id"] == success_case.id
    assert response.data["status"] == SuccessCase.STATUS_INVALIDATED

    success_case.refresh_from_db()
    card.refresh_from_db()
    card.male_user.refresh_from_db()
    card.female_user.refresh_from_db()
    oplog = OperationLog.objects.get(
        action="success_invalidated",
        target_type="success_case",
        target_id=success_case.id,
    )

    assert success_case.status == SuccessCase.STATUS_INVALIDATED
    assert success_case.invalidated_reason_id == invalidate_reason.id
    assert success_case.invalidated_reason_note == "关系结束，标记成功失效"
    assert success_case.invalidated_at is not None
    assert card.stage == MatchCard.STAGE_ENDED
    assert card.ended_at is not None
    assert card.next_remind_at is None
    assert card.male_user.is_in_match is False
    assert card.female_user.is_in_match is False
    assert card.male_user.pool_status == male_pool_status
    assert card.female_user.pool_status == female_pool_status
    assert oplog.operator_id == primary_staff.id
    assert oplog.reason == "关系结束，标记成功失效"


def test_admin_can_invalidate_success_case(
    auth_client,
    admin_staff,
    create_success_case,
    create_reason_enum,
):
    success_case = create_success_case()
    invalidate_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
        label="双方关系失效",
    )

    response = auth_client(admin_staff).post(
        f"/api/v1/success-cases/{success_case.id}/invalidate/",
        {"reason_id": invalidate_reason.id},
        format="json",
    )

    assert response.status_code == 200
    success_case.refresh_from_db()
    assert success_case.status == SuccessCase.STATUS_INVALIDATED


def test_non_primary_matchmaker_cannot_invalidate_success_case(
    auth_client,
    create_match_card,
    create_success_application,
    create_success_case,
    create_reason_enum,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘M")
    female_staff = create_staff(name="女方红娘M")
    card = create_match_card(primary_staff=primary_staff, male_staff=primary_staff, female_staff=female_staff)
    application = create_success_application(match_card=card, applicant=primary_staff, status=SuccessApplication.STATUS_APPROVED)
    success_case = create_success_case(match_card=card, application=application)
    invalidate_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
        label="双方关系破裂",
    )

    response = auth_client(female_staff).post(
        f"/api/v1/success-cases/{success_case.id}/invalidate/",
        {"reason_id": invalidate_reason.id},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"


def test_success_case_invalidate_requires_success_invalidate_reason(
    auth_client,
    create_success_case,
    create_reason_enum,
    create_staff,
):
    primary_staff = create_staff(name="主操作红娘N")
    success_case = create_success_case()
    success_case.match_card.primary_staff = primary_staff
    success_case.match_card.male_staff = primary_staff
    success_case.match_card.save(update_fields=["primary_staff", "male_staff", "updated_at"])
    pause_reason = create_reason_enum(
        category=ReasonEnum.CATEGORY_PAUSE,
        label="忙工作-失效测试",
    )

    response = auth_client(primary_staff).post(
        f"/api/v1/success-cases/{success_case.id}/invalidate/",
        {"reason_id": pause_reason.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "reason_id" in response.data["details"]
