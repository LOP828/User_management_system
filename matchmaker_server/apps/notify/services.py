import json
import logging
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from apps.reminder.models import Reminder
from apps.staff.models import Staff
from apps.success.models import SuccessApplication
from apps.transfer.models import UserTransferRequest


logger = logging.getLogger(__name__)

EVENT_TRANSFER_APPLIED = "transfer_applied"
EVENT_SUCCESS_APPLIED = "success_applied"
EVENT_SUCCESS_APPROVED = "success_approved"
EVENT_SUCCESS_REJECTED = "success_rejected"
EVENT_REMINDER_DUE = "reminder_due"

PHASE1_EVENT_TYPES = {
    EVENT_TRANSFER_APPLIED,
    EVENT_SUCCESS_APPLIED,
    EVENT_SUCCESS_APPROVED,
    EVENT_SUCCESS_REJECTED,
}
PHASE1_REMINDER_TYPES = {
    Reminder.TYPE_MANUAL,
    Reminder.TYPE_FOLLOWUP_TIMEOUT,
    Reminder.TYPE_PAUSE_REVISIT,
    Reminder.TYPE_FIRST_MEET_PENDING,
    Reminder.TYPE_FIRST_MEET_DELAYED,
    Reminder.TYPE_FIRST_MEET_WARNING,
    Reminder.TYPE_FIRST_MEET_OVERDUE,
    Reminder.TYPE_SUCCESS_REVISIT,
}


def notify_enabled():
    return bool(getattr(settings, "WECOM_NOTIFY_ENABLED", False))


def reminder_due_enabled():
    return bool(getattr(settings, "WECOM_NOTIFY_REMINDER_DUE_ENABLED", False))


def enqueue_phase1_event_safely(task_func, event_type, entity_id):
    try:
        task_func.delay(event_type, entity_id)
    except Exception:
        logger.exception(
            "Failed to enqueue notify phase1 event",
            extra={"event_type": event_type, "entity_id": entity_id},
        )
        return False
    return True


def get_wecom_webhook_url():
    return (getattr(settings, "WECOM_WEBHOOK_URL", "") or "").strip()


def _staff_mention_payload(staff_members):
    mentioned_list = []
    mentioned_mobile_list = []
    for staff in staff_members:
        if staff.wechat_id:
            mentioned_list.append(staff.wechat_id)
        if staff.phone:
            mentioned_mobile_list.append(staff.phone)
    return mentioned_list, mentioned_mobile_list


def send_wecom_text(content, *, staff_members=None):
    webhook_url = get_wecom_webhook_url()
    if not notify_enabled():
        return {"ok": False, "skipped": True, "reason": "notify_disabled"}
    if not webhook_url:
        logger.warning("WECOM_NOTIFY_ENABLED=true but WECOM_WEBHOOK_URL is empty")
        return {"ok": False, "skipped": True, "reason": "missing_webhook_url"}

    mentioned_list, mentioned_mobile_list = _staff_mention_payload(staff_members or [])
    payload = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": mentioned_list,
            "mentioned_mobile_list": mentioned_mobile_list,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = int(getattr(settings, "WECOM_NOTIFY_TIMEOUT_SECONDS", 5))
    logger.info(
        "Sending WeCom webhook",
        extra={
            "mentioned_list_count": len(mentioned_list),
            "mentioned_mobile_list_count": len(mentioned_mobile_list),
            "content_preview": content.splitlines()[0][:80] if content else "",
            "timeout_seconds": timeout,
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.URLError:
        logger.exception("Failed to send WeCom webhook")
        raise

    parsed = json.loads(body)
    if parsed.get("errcode") != 0:
        logger.error("WeCom webhook returned non-zero errcode: %s", parsed)
        raise RuntimeError(f"WeCom webhook failed: {parsed}")
    logger.info(
        "WeCom webhook delivered",
        extra={"errcode": parsed.get("errcode"), "errmsg": parsed.get("errmsg")},
    )
    return {"ok": True, "response": parsed}


def _active_admin_receivers():
    return list(
        Staff.objects.filter(role=Staff.ROLE_ADMIN, status=Staff.STATUS_ACTIVE).order_by("id")
    )


def _format_dt(value):
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _build_transfer_applied_message(transfer_request):
    return (
        "[AI红娘系统] 转移申请待审批\n"
        f"用户：{transfer_request.user.name}#{transfer_request.user_id}\n"
        f"发起人：{transfer_request.from_staff.name}\n"
        f"目标红娘：{transfer_request.to_staff.name}\n"
        f"申请时间：{_format_dt(transfer_request.created_at)}\n"
        f"原因：{transfer_request.reason}"
    )


def _build_success_applied_message(application):
    match_card = application.match_card
    return (
        "[AI红娘系统] 成功申请待审批\n"
        f"配对卡：#{match_card.id}\n"
        f"配对双方：{match_card.male_user.name} × {match_card.female_user.name}\n"
        f"申请人：{application.applicant.name}\n"
        f"申请时间：{_format_dt(application.created_at)}\n"
        f"说明：{application.apply_note or '-'}"
    )


def _build_success_approved_message(application):
    match_card = application.match_card
    return (
        "[AI红娘系统] 成功申请审批通过\n"
        f"申请ID：#{application.id}\n"
        f"配对卡：#{match_card.id}\n"
        f"配对双方：{match_card.male_user.name} × {match_card.female_user.name}\n"
        f"申请人：{application.applicant.name}\n"
        f"审批时间：{_format_dt(application.reviewed_at)}"
    )


def _build_success_rejected_message(application):
    match_card = application.match_card
    return (
        "[AI红娘系统] 成功申请审批驳回\n"
        f"申请ID：#{application.id}\n"
        f"配对卡：#{match_card.id}\n"
        f"配对双方：{match_card.male_user.name} × {match_card.female_user.name}\n"
        f"申请人：{application.applicant.name}\n"
        f"审批时间：{_format_dt(application.reviewed_at)}\n"
        f"驳回原因：{application.review_note or '-'}"
    )


def _build_reminder_due_message(reminder):
    from apps.reminder.services import build_reminder_display

    display = build_reminder_display(reminder)
    return (
        "[AI红娘系统] Reminder 到期通知\n"
        f"提醒ID：#{reminder.id}\n"
        f"提醒类型：{display['remind_type_display']}\n"
        f"对象：{display['target_name']}\n"
        f"摘要：{display['target_summary']}\n"
        f"接收人：{reminder.staff.name}"
    )


def send_transfer_applied_notification(transfer_request_id):
    transfer_request = UserTransferRequest.objects.select_related(
        "user",
        "from_staff",
        "to_staff",
    ).get(id=transfer_request_id)
    admins = _active_admin_receivers()
    return send_wecom_text(_build_transfer_applied_message(transfer_request), staff_members=admins)


def send_success_applied_notification(application_id):
    application = SuccessApplication.objects.select_related(
        "applicant",
        "match_card__male_user",
        "match_card__female_user",
        "match_card__primary_staff",
    ).get(id=application_id)
    admins = _active_admin_receivers()
    return send_wecom_text(_build_success_applied_message(application), staff_members=admins)


def _success_result_receivers(application):
    receivers = []
    seen = set()
    for staff in (application.applicant, application.match_card.primary_staff):
        if staff and staff.id not in seen:
            receivers.append(staff)
            seen.add(staff.id)
    return receivers


def send_success_approved_notification(application_id):
    application = SuccessApplication.objects.select_related(
        "applicant",
        "match_card__male_user",
        "match_card__female_user",
        "match_card__primary_staff",
    ).get(id=application_id)
    return send_wecom_text(
        _build_success_approved_message(application),
        staff_members=_success_result_receivers(application),
    )


def send_success_rejected_notification(application_id):
    application = SuccessApplication.objects.select_related(
        "applicant",
        "match_card__male_user",
        "match_card__female_user",
        "match_card__primary_staff",
    ).get(id=application_id)
    return send_wecom_text(
        _build_success_rejected_message(application),
        staff_members=_success_result_receivers(application),
    )


def send_due_reminder_notifications(*, limit=100):
    if not reminder_due_enabled():
        return {"sent": 0, "skipped": "reminder_due_disabled"}
    queryset = (
        Reminder.objects.select_related("staff")
        .filter(
            status=Reminder.STATUS_PENDING,
            remind_at__lte=timezone.now(),
            remind_type__in=PHASE1_REMINDER_TYPES,
        )
        .order_by("remind_at", "id")[:limit]
    )

    sent = 0
    for reminder in queryset:
        result = send_wecom_text(
            _build_reminder_due_message(reminder),
            staff_members=[reminder.staff],
        )
        if result.get("ok"):
            updated = Reminder.objects.filter(
                id=reminder.id,
                status=Reminder.STATUS_PENDING,
            ).update(status=Reminder.STATUS_SENT)
            sent += updated
    return {"sent": sent}
