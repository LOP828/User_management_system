from django.db import models


class ReasonEnum(models.Model):
    CATEGORY_PAUSE = "pause"
    CATEGORY_MEET_FAILURE = "meet_failure"
    CATEGORY_OVERDUE = "overdue"
    CATEGORY_RISK = "risk"
    CATEGORY_TRANSFER = "transfer"
    CATEGORY_SUCCESS_INVALIDATE = "success_invalidate"
    CATEGORY_MATCH_END = "match_end"

    CATEGORY_CHOICES = (
        (CATEGORY_PAUSE, "pause"),
        (CATEGORY_MEET_FAILURE, "meet_failure"),
        (CATEGORY_OVERDUE, "overdue"),
        (CATEGORY_RISK, "risk"),
        (CATEGORY_TRANSFER, "transfer"),
        (CATEGORY_SUCCESS_INVALIDATE, "success_invalidate"),
        (CATEGORY_MATCH_END, "match_end"),
    )

    id = models.BigAutoField(primary_key=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    label = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reason_enum"
        indexes = [
            models.Index(fields=["category", "is_active", "sort_order"], name="reason_enum_cat_idx"),
        ]


class PaymentLevel(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    homepage_weight = models.IntegerField(default=0)
    recommend_limit = models.IntegerField()
    pause_revisit_days = models.IntegerField(default=30)
    followup_timeout_days = models.IntegerField(default=7)
    note = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_level"
        indexes = [
            models.Index(fields=["is_active", "sort_order"], name="payment_level_idx"),
        ]
