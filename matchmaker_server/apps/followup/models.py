from django.conf import settings
from django.db import models

from apps.config_mgmt.models import ReasonEnum
from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


class FollowUpRecord(models.Model):
    SCENE_UNMATCHED = "unmatched"
    SCENE_MATCHED = "matched"
    SCENE_SUCCESS_FOLLOWUP = "success_followup"
    SCENE_CHOICES = (
        (SCENE_UNMATCHED, "unmatched"),
        (SCENE_MATCHED, "matched"),
        (SCENE_SUCCESS_FOLLOWUP, "success_followup"),
    )

    REMIND_MANUAL = "manual"
    REMIND_DEFAULT = "default"
    NEXT_REMIND_MODE_CHOICES = (
        (REMIND_MANUAL, "manual"),
        (REMIND_DEFAULT, "default"),
    )

    CONTACT_YES = "yes"
    CONTACT_NO = "no"
    CONTACT_UNKNOWN = "unknown"
    CONTACT_STATUS_CHOICES = (
        (CONTACT_YES, "yes"),
        (CONTACT_NO, "no"),
        (CONTACT_UNKNOWN, "unknown"),
    )

    RISK_NONE = "none"
    RISK_WATCHING = "watching"
    RISK_HIGH_RISK = "high_risk"
    RISK_STATUS_CHOICES = (
        (RISK_NONE, "none"),
        (RISK_WATCHING, "watching"),
        (RISK_HIGH_RISK, "high_risk"),
    )

    id = models.BigAutoField(primary_key=True)
    scene = models.CharField(max_length=20, choices=SCENE_CHOICES)
    user = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="follow_ups",
        db_column="user_id",
    )
    match_card = models.ForeignKey(
        MatchCard,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="follow_ups",
        db_column="match_card_id",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="follow_ups",
        db_column="staff_id",
    )
    content = models.TextField()
    next_remind_mode = models.CharField(
        max_length=10,
        choices=NEXT_REMIND_MODE_CHOICES,
        null=True,
        blank=True,
    )
    next_remind_at = models.DateTimeField(null=True, blank=True)
    is_still_contact = models.CharField(
        max_length=10,
        choices=CONTACT_STATUS_CHOICES,
        null=True,
        blank=True,
    )
    risk_status = models.CharField(
        max_length=20,
        choices=RISK_STATUS_CHOICES,
        null=True,
        blank=True,
    )
    failure_reason = models.ForeignKey(
        ReasonEnum,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failure_follow_ups",
        db_column="failure_reason_id",
    )
    overdue_reason = models.ForeignKey(
        ReasonEnum,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overdue_follow_ups",
        db_column="overdue_reason_id",
    )
    overdue_reason_note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follow_up_record"
        indexes = [
            models.Index(fields=["user", "created_at"], name="follow_up_user_created_idx"),
            models.Index(fields=["match_card", "created_at"], name="follow_up_match_created_idx"),
            models.Index(fields=["staff"], name="follow_up_staff_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scene__in=["unmatched", "matched", "success_followup"]),
                name="follow_up_scene_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(next_remind_mode__isnull=True)
                | models.Q(next_remind_mode__in=["manual", "default"]),
                name="follow_up_next_remind_mode_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(is_still_contact__isnull=True)
                | models.Q(is_still_contact__in=["yes", "no", "unknown"]),
                name="follow_up_contact_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(risk_status__isnull=True)
                | models.Q(risk_status__in=["none", "watching", "high_risk"]),
                name="follow_up_risk_status_valid",
            ),
        ]
