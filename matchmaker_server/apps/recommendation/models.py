from django.conf import settings
from django.db import models


class RecommendationBatch(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = (
        (STATUS_OPEN, "open"),
        (STATUS_CLOSED, "closed"),
    )

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        "user.CustomerProfile",
        on_delete=models.PROTECT,
        related_name="recommendation_batches",
        db_column="user_id",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recommendation_batches",
        db_column="staff_id",
    )
    batch_no = models.CharField(max_length=50, unique=True)
    candidate_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recommendation_batch"
        indexes = [
            models.Index(fields=["user", "created_at"], name="rec_batch_user_created_idx"),
            models.Index(fields=["staff"], name="rec_batch_staff_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["open", "closed"]),
                name="rec_batch_status_valid",
            ),
        ]


class RecommendationCandidate(models.Model):
    RESULT_CONTINUE = "continue"
    RESULT_NOT_CONTINUE = "not_continue"
    RESULT_PENDING = "pending"
    RESULT_CHOICES = (
        (RESULT_CONTINUE, "continue"),
        (RESULT_NOT_CONTINUE, "not_continue"),
        (RESULT_PENDING, "pending"),
    )

    id = models.BigAutoField(primary_key=True)
    batch = models.ForeignKey(
        RecommendationBatch,
        on_delete=models.PROTECT,
        related_name="candidates",
        db_column="batch_id",
    )
    candidate_user = models.ForeignKey(
        "user.CustomerProfile",
        on_delete=models.PROTECT,
        related_name="recommended_as_candidates",
        db_column="candidate_user_id",
    )
    is_selected = models.BooleanField(default=False)
    is_met = models.BooleanField(default=False)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recommendation_candidate"
        indexes = [
            models.Index(fields=["batch"], name="rec_candidate_batch_idx"),
            models.Index(fields=["candidate_user"], name="rec_candidate_user_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(result__isnull=True) | models.Q(result__in=["continue", "not_continue", "pending"]),
                name="rec_candidate_result_valid",
            ),
        ]
