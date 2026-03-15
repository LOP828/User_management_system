from django.conf import settings
from django.db import models

from apps.config_mgmt.models import ReasonEnum
from apps.matchcard.models import MatchCard


class SuccessApplication(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "pending"),
        (STATUS_APPROVED, "approved"),
        (STATUS_REJECTED, "rejected"),
    )

    id = models.BigAutoField(primary_key=True)
    match_card = models.ForeignKey(
        MatchCard,
        on_delete=models.PROTECT,
        related_name="success_applications",
        db_column="match_card_id",
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="success_applications",
        db_column="applicant_id",
    )
    apply_note = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_success_applications",
        db_column="reviewer_id",
    )
    review_note = models.CharField(max_length=500, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "success_application"
        indexes = [
            models.Index(fields=["match_card"], name="success_app_match_card_idx"),
            models.Index(fields=["status"], name="success_app_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "approved", "rejected"]),
                name="success_app_status_valid",
            ),
        ]


class SuccessCase(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INVALIDATED = "invalidated"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "active"),
        (STATUS_INVALIDATED, "invalidated"),
    )

    id = models.BigAutoField(primary_key=True)
    match_card = models.ForeignKey(
        MatchCard,
        on_delete=models.PROTECT,
        related_name="success_cases",
        db_column="match_card_id",
    )
    application = models.ForeignKey(
        SuccessApplication,
        on_delete=models.PROTECT,
        related_name="success_cases",
        db_column="application_id",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    invalidated_reason = models.ForeignKey(
        ReasonEnum,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invalidated_success_cases",
        db_column="invalidated_reason_id",
    )
    invalidated_reason_note = models.CharField(max_length=500, null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "success_case"
        indexes = [
            models.Index(fields=["status"], name="success_case_status_idx"),
            models.Index(fields=["approved_at"], name="success_case_approved_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "invalidated"]),
                name="success_case_status_valid",
            ),
        ]
