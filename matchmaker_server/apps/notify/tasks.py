import logging

from celery import shared_task

from apps.notify.services import (
    EVENT_SUCCESS_APPLIED,
    EVENT_SUCCESS_APPROVED,
    EVENT_SUCCESS_REJECTED,
    EVENT_TRANSFER_APPLIED,
    send_due_reminder_notifications,
    send_success_applied_notification,
    send_success_approved_notification,
    send_success_rejected_notification,
    send_transfer_applied_notification,
)


logger = logging.getLogger(__name__)


@shared_task(name="notify.send_phase1_event")
def send_phase1_event(event_type, entity_id):
    logger.info("notify.send_phase1_event received", extra={"event_type": event_type, "entity_id": entity_id})
    if event_type == EVENT_TRANSFER_APPLIED:
        result = send_transfer_applied_notification(entity_id)
        logger.info(
            "notify.send_phase1_event completed",
            extra={"event_type": event_type, "entity_id": entity_id, "result": result},
        )
        return result
    if event_type == EVENT_SUCCESS_APPLIED:
        result = send_success_applied_notification(entity_id)
        logger.info(
            "notify.send_phase1_event completed",
            extra={"event_type": event_type, "entity_id": entity_id, "result": result},
        )
        return result
    if event_type == EVENT_SUCCESS_APPROVED:
        result = send_success_approved_notification(entity_id)
        logger.info(
            "notify.send_phase1_event completed",
            extra={"event_type": event_type, "entity_id": entity_id, "result": result},
        )
        return result
    if event_type == EVENT_SUCCESS_REJECTED:
        result = send_success_rejected_notification(entity_id)
        logger.info(
            "notify.send_phase1_event completed",
            extra={"event_type": event_type, "entity_id": entity_id, "result": result},
        )
        return result
    raise ValueError(f"Unsupported phase1 event_type: {event_type}")


@shared_task(name="notify.send_due_reminders")
def send_due_reminders():
    return send_due_reminder_notifications()
