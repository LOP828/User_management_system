from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.matchcard.models import MatchCard
from apps.notify.services import send_due_reminder_notifications
from apps.followup.models import FollowUpRecord
from apps.reminder.models import Reminder
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_transfer_applied_queues_phase1_event(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
    create_staff,
    django_capture_on_commit_callbacks,
):
    to_staff = create_staff(name="目标红娘")
    suffix = f"{uuid4().int % 10**8:08d}"
    user = create_customer_profile(
        owner=matchmaker_staff,
        phone=f"138{suffix}",
        wechat=f"wx_{suffix}",
    )

    with patch("apps.notify.tasks.send_phase1_event.delay") as delay_mock:
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(matchmaker_staff).post(
                "/api/v1/transfer-requests/",
                data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "本人即将休假"},
                format="json",
            )

    assert response.status_code == 201
    transfer_request_id = response.json()["id"]
    delay_mock.assert_called_once_with("transfer_applied", transfer_request_id)


def _seed_success_application_prerequisites(match_card, *, male_count=2, female_count=2):
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
    match_card.staff_judgment = "主操作红娘确认双方已建立恋爱关系"
    match_card.save(update_fields=["staff_judgment", "updated_at"])


def _make_pending_success_application(create_staff, create_customer_profile):
    from apps.success.models import SuccessApplication

    primary_staff = create_staff(name="主操作红娘")
    female_staff = create_staff(name="女方红娘")
    suffix = f"{uuid4().int % 10**8:08d}"
    male_user = create_customer_profile(
        owner=primary_staff,
        gender=CustomerProfile.GENDER_MALE,
        phone=f"139{suffix}",
        wechat=f"male_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        phone=f"137{suffix}",
        wechat=f"female_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    card = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=primary_staff,
        female_staff=female_staff,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
        risk_level=MatchCard.RISK_NONE,
    )
    application = SuccessApplication.objects.create(
        match_card=card,
        applicant=primary_staff,
        apply_note="双方关系稳定",
        status=SuccessApplication.STATUS_PENDING,
    )
    return application


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_success_applied_queues_phase1_event(
    auth_client,
    create_staff,
    create_customer_profile,
    django_capture_on_commit_callbacks,
):
    primary_staff = create_staff(name="主操作红娘")
    female_staff = create_staff(name="女方红娘")
    suffix = f"{uuid4().int % 10**8:08d}"
    male_user = create_customer_profile(
        owner=primary_staff,
        gender=CustomerProfile.GENDER_MALE,
        phone=f"139{suffix}",
        wechat=f"male_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        phone=f"137{suffix}",
        wechat=f"female_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    card = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=primary_staff,
        female_staff=female_staff,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
        risk_level=MatchCard.RISK_NONE,
    )
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    _seed_success_application_prerequisites(card)

    with patch("apps.notify.tasks.send_phase1_event.delay") as delay_mock:
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(primary_staff).post(
                "/api/v1/success-applications/",
                {"match_card_id": card.id, "apply_note": "双方交往稳定"},
                format="json",
            )

    assert response.status_code == 201
    application_id = response.json()["id"]
    delay_mock.assert_called_once_with("success_applied", application_id)


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_NOTIFY_REMINDER_DUE_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_send_due_reminders_only_sends_persisted_phase1_types(matchmaker_staff, create_customer_profile):
    user = create_customer_profile(owner=matchmaker_staff)
    due_manual = Reminder.objects.create(
        target_type=Reminder.TARGET_USER,
        target_id=user.id,
        staff=matchmaker_staff,
        remind_type=Reminder.TYPE_MANUAL,
        remind_at=timezone.now() - timedelta(minutes=1),
        status=Reminder.STATUS_PENDING,
        is_manual=True,
    )
    Reminder.objects.create(
        target_type=Reminder.TARGET_MATCH_CARD,
        target_id=999,
        staff=matchmaker_staff,
        remind_type=Reminder.TYPE_MATCHED_REVISIT,
        remind_at=timezone.now() - timedelta(minutes=1),
        status=Reminder.STATUS_PENDING,
        is_manual=False,
    )

    with patch("apps.notify.services.send_wecom_text", return_value={"ok": True}) as send_mock:
        result = send_due_reminder_notifications()

    assert result["sent"] == 1
    due_manual.refresh_from_db()
    assert due_manual.status == Reminder.STATUS_SENT
    assert send_mock.call_count == 1
    assert not Reminder.objects.filter(remind_type=Reminder.TYPE_MATCHED_REVISIT, status=Reminder.STATUS_SENT).exists()


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_transfer_applied_delay_error_does_not_break_main_request(
    auth_client,
    matchmaker_staff,
    create_customer_profile,
    create_staff,
    django_capture_on_commit_callbacks,
):
    to_staff = create_staff(name="目标红娘")
    suffix = f"{uuid4().int % 10**8:08d}"
    user = create_customer_profile(
        owner=matchmaker_staff,
        phone=f"138{suffix}",
        wechat=f"wx_{suffix}",
    )

    with patch(
        "apps.notify.tasks.send_phase1_event.delay",
        side_effect=RuntimeError("celery backend reconnect failed"),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(matchmaker_staff).post(
                "/api/v1/transfer-requests/",
                data={"user_id": user.id, "to_staff_id": to_staff.id, "reason": "本人即将休假"},
                format="json",
            )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_success_applied_delay_error_does_not_break_main_request(
    auth_client,
    create_staff,
    create_customer_profile,
    django_capture_on_commit_callbacks,
):
    primary_staff = create_staff(name="主操作红娘")
    female_staff = create_staff(name="女方红娘")
    suffix = f"{uuid4().int % 10**8:08d}"
    male_user = create_customer_profile(
        owner=primary_staff,
        gender=CustomerProfile.GENDER_MALE,
        phone=f"139{suffix}",
        wechat=f"male_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    female_user = create_customer_profile(
        owner=female_staff,
        gender=CustomerProfile.GENDER_FEMALE,
        phone=f"137{suffix}",
        wechat=f"female_{suffix}",
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
    )
    card = MatchCard.objects.create(
        male_user=male_user,
        female_user=female_user,
        male_staff=primary_staff,
        female_staff=female_staff,
        primary_staff=primary_staff,
        stage=MatchCard.STAGE_STABLE_CONTACT,
        risk_level=MatchCard.RISK_NONE,
    )
    MatchCard.objects.filter(pk=card.pk).update(created_at=timezone.now() - timedelta(days=31))
    card.refresh_from_db()
    _seed_success_application_prerequisites(card)

    with patch(
        "apps.notify.tasks.send_phase1_event.delay",
        side_effect=RuntimeError("celery backend reconnect failed"),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(primary_staff).post(
                "/api/v1/success-applications/",
                {"match_card_id": card.id, "apply_note": "双方交往稳定"},
                format="json",
            )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_success_approved_queues_phase1_event(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
    django_capture_on_commit_callbacks,
):
    application = _make_pending_success_application(create_staff, create_customer_profile)

    with patch("apps.notify.tasks.send_phase1_event.delay") as delay_mock:
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(admin_staff).post(
                f"/api/v1/success-applications/{application.id}/approve/"
            )

    assert response.status_code == 200
    delay_mock.assert_called_once_with("success_approved", application.id)


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_success_rejected_queues_phase1_event(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
    django_capture_on_commit_callbacks,
):
    application = _make_pending_success_application(create_staff, create_customer_profile)

    with patch("apps.notify.tasks.send_phase1_event.delay") as delay_mock:
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(admin_staff).post(
                f"/api/v1/success-applications/{application.id}/reject/",
                {"review_note": "资料需补充"},
                format="json",
            )

    assert response.status_code == 200
    delay_mock.assert_called_once_with("success_rejected", application.id)


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_success_approved_delay_error_does_not_break_main_request(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
    django_capture_on_commit_callbacks,
):
    application = _make_pending_success_application(create_staff, create_customer_profile)

    with patch(
        "apps.notify.tasks.send_phase1_event.delay",
        side_effect=RuntimeError("celery backend reconnect failed"),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(admin_staff).post(
                f"/api/v1/success-applications/{application.id}/approve/"
            )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


@override_settings(
    WECOM_NOTIFY_ENABLED=True,
    WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
)
def test_success_rejected_delay_error_does_not_break_main_request(
    auth_client,
    admin_staff,
    create_staff,
    create_customer_profile,
    django_capture_on_commit_callbacks,
):
    application = _make_pending_success_application(create_staff, create_customer_profile)

    with patch(
        "apps.notify.tasks.send_phase1_event.delay",
        side_effect=RuntimeError("celery backend reconnect failed"),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client(admin_staff).post(
                f"/api/v1/success-applications/{application.id}/reject/",
                {"review_note": "资料需补充"},
                format="json",
            )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
