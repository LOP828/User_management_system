from django.conf import settings
from django.db import models


class Reminder(models.Model):
    TARGET_USER = "user"
    TARGET_MATCH_CARD = "match_card"
    TARGET_TYPE_CHOICES = (
        (TARGET_USER, "user"),
        (TARGET_MATCH_CARD, "match_card"),
    )

    TYPE_NORMAL = "normal"
    TYPE_FIRST_MEET_PENDING = "first_meet_pending"
    TYPE_FIRST_MEET_DELAYED = "first_meet_delayed"
    TYPE_FIRST_MEET_WARNING = "first_meet_warning"
    TYPE_FIRST_MEET_OVERDUE = "first_meet_overdue"
    TYPE_FOLLOWUP_TIMEOUT = "followup_timeout"
    TYPE_PAUSE_REVISIT = "pause_revisit"
    TYPE_MATCHED_REVISIT = "matched_revisit"
    TYPE_SUCCESS_REVISIT = "success_revisit"
    TYPE_URGENT = "urgent"
    TYPE_MANUAL = "manual"
    REMIND_TYPE_CHOICES = (
        (TYPE_NORMAL, "normal"),
        (TYPE_FIRST_MEET_PENDING, "first_meet_pending"),
        (TYPE_FIRST_MEET_DELAYED, "first_meet_delayed"),
        (TYPE_FIRST_MEET_WARNING, "first_meet_warning"),
        (TYPE_FIRST_MEET_OVERDUE, "first_meet_overdue"),
        (TYPE_FOLLOWUP_TIMEOUT, "followup_timeout"),
        (TYPE_PAUSE_REVISIT, "pause_revisit"),
        (TYPE_MATCHED_REVISIT, "matched_revisit"),
        (TYPE_SUCCESS_REVISIT, "success_revisit"),
        (TYPE_URGENT, "urgent"),
        (TYPE_MANUAL, "manual"),
    )

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_PROCESSED = "processed"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = (
        (STATUS_PENDING, "pending"),
        (STATUS_SENT, "sent"),
        (STATUS_PROCESSED, "processed"),
        (STATUS_EXPIRED, "expired"),
    )

    id = models.BigAutoField(primary_key=True)
    target_type = models.CharField(max_length=20, choices=TARGET_TYPE_CHOICES)
    target_id = models.BigIntegerField()
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reminders",
        db_column="staff_id",
    )
    remind_type = models.CharField(max_length=30, choices=REMIND_TYPE_CHOICES)
    remind_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    processed_at = models.DateTimeField(null=True, blank=True)
    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reminder"
        indexes = [
            models.Index(fields=["staff", "status", "remind_at"], name="reminder_staff_status_time_idx"),
            models.Index(fields=["target_type", "target_id"], name="reminder_target_idx"),
            models.Index(fields=["remind_at", "status"], name="reminder_time_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(target_type__in=["user", "match_card"]),
                name="reminder_target_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    remind_type__in=[
                        "normal",
                        "first_meet_pending",
                        "first_meet_delayed",
                        "first_meet_warning",
                        "first_meet_overdue",
                        "followup_timeout",
                        "pause_revisit",
                        "matched_revisit",
                        "success_revisit",
                        "urgent",
                        "manual",
                    ]
                ),
                name="reminder_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "sent",
                        "processed",
                        "expired",
                    ]
                ),
                name="reminder_status_valid",
            ),
        ]
