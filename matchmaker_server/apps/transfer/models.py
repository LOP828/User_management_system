from django.conf import settings
from django.db import models


class UserTransferRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_APPROVED, "approved"),
        (STATUS_REJECTED, "rejected"),
    ]

    user = models.ForeignKey(
        "user.CustomerProfile",
        db_column="user_id",
        on_delete=models.PROTECT,
        related_name="transfer_requests",
    )
    from_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="from_staff_id",
        on_delete=models.PROTECT,
        related_name="transfer_requests_sent",
    )
    to_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="to_staff_id",
        on_delete=models.PROTECT,
        related_name="transfer_requests_received",
    )
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="reviewer_id",
        on_delete=models.PROTECT,
        related_name="transfer_requests_reviewed",
        null=True,
        blank=True,
    )
    review_note = models.CharField(max_length=500, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_transfer_request"
        indexes = [
            models.Index(fields=["user"], name="transfer_req_user_idx"),
            models.Index(fields=["status"], name="transfer_req_status_idx"),
            models.Index(fields=["from_staff"], name="transfer_req_from_staff_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "approved", "rejected"]),
                name="transfer_req_status_valid",
            )
        ]
