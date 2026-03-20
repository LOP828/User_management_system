from django.conf import settings
from django.db import models

from apps.config_mgmt.models import PaymentLevel, ReasonEnum


class CustomerProfile(models.Model):
    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_CHOICES = (
        (GENDER_MALE, "male"),
        (GENDER_FEMALE, "female"),
    )

    STATUS_NEW_PENDING = "new_pending"
    STATUS_COMMUNICATED_PENDING_RECOMMEND = "communicated_pending_recommend"
    STATUS_RECOMMENDED_PENDING_SELECT = "recommended_pending_select"
    STATUS_SELECTED_PENDING_MEET = "selected_pending_meet"
    STATUS_MET_NOT_CONTINUE = "met_not_continue"
    STATUS_PAUSED = "paused"
    POOL_STATUS_CHOICES = (
        (STATUS_NEW_PENDING, "new_pending"),
        (STATUS_COMMUNICATED_PENDING_RECOMMEND, "communicated_pending_recommend"),
        (STATUS_RECOMMENDED_PENDING_SELECT, "recommended_pending_select"),
        (STATUS_SELECTED_PENDING_MEET, "selected_pending_meet"),
        (STATUS_MET_NOT_CONTINUE, "met_not_continue"),
        (STATUS_PAUSED, "paused"),
    )

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age = models.PositiveIntegerField()
    phone = models.CharField(max_length=20, null=True, blank=True)
    wechat = models.CharField(max_length=100, null=True, blank=True)
    other_contact = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=50)
    payment_level = models.ForeignKey(PaymentLevel, on_delete=models.PROTECT, related_name="users")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_users")
    basic_requirement = models.TextField()
    pool_status = models.CharField(max_length=30, choices=POOL_STATUS_CHOICES, default=STATUS_NEW_PENDING)
    pre_pause_status = models.CharField(max_length=30, null=True, blank=True)
    is_profile_complete = models.BooleanField(default=False)
    is_in_match = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    last_action_at = models.DateTimeField(null=True, blank=True)
    last_unmatched_active_at = models.DateTimeField(null=True, blank=True)
    profile_detail = models.JSONField(null=True, blank=True)
    emotional_history = models.JSONField(null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user"
        indexes = [
            models.Index(fields=["owner"], name="user_owner_idx"),
            models.Index(fields=["pool_status"], name="user_pool_status_idx"),
            models.Index(fields=["payment_level"], name="user_payment_level_idx"),
            models.Index(fields=["is_in_match"], name="user_is_in_match_idx"),
            models.Index(fields=["city"], name="user_city_idx"),
            models.Index(fields=["created_at"], name="user_created_at_idx"),
            models.Index(fields=["paid_at"], name="user_paid_at_idx"),
            models.Index(fields=["last_unmatched_active_at"], name="user_last_unmatched_active_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(gender__in=["male", "female"]),
                name="customer_profile_gender_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    pool_status__in=[
                        "new_pending",
                        "communicated_pending_recommend",
                        "recommended_pending_select",
                        "selected_pending_meet",
                        "met_not_continue",
                        "paused",
                    ]
                ),
                name="customer_profile_pool_status_valid",
            ),
        ]


class UserStatusHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="status_histories")
    from_status = models.CharField(max_length=30, null=True, blank=True)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="user_status_changes")
    reason = models.CharField(max_length=500, null=True, blank=True)
    reason_id = models.ForeignKey(
        ReasonEnum,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_status_histories",
        db_column="reason_id",
    )
    reason_note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_status_history"
        indexes = [
            models.Index(fields=["user", "created_at"], name="user_status_history_idx"),
        ]
