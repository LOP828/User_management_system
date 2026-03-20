from django.conf import settings
from django.db import models

from apps.config_mgmt.models import ReasonEnum
from apps.recommendation.models import RecommendationCandidate
from apps.user.models import CustomerProfile


class MatchCard(models.Model):
    STAGE_INITIAL_CONTACT = "initial_contact"
    STAGE_STABLE_CONTACT = "stable_contact"
    STAGE_SUCCESS_PENDING_REVIEW = "success_pending_review"
    STAGE_SUCCESS = "success"
    STAGE_ENDED = "ended"
    STAGE_CHOICES = (
        (STAGE_INITIAL_CONTACT, "initial_contact"),
        (STAGE_STABLE_CONTACT, "stable_contact"),
        (STAGE_SUCCESS_PENDING_REVIEW, "success_pending_review"),
        (STAGE_SUCCESS, "success"),
        (STAGE_ENDED, "ended"),
    )

    RISK_NONE = "none"
    RISK_WATCHING = "watching"
    RISK_HIGH_RISK = "high_risk"
    RISK_LEVEL_CHOICES = (
        (RISK_NONE, "none"),
        (RISK_WATCHING, "watching"),
        (RISK_HIGH_RISK, "high_risk"),
    )

    id = models.BigAutoField(primary_key=True)
    male_user = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="male_match_cards",
        db_column="male_user_id",
    )
    female_user = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="female_match_cards",
        db_column="female_user_id",
    )
    male_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="male_side_match_cards",
        db_column="male_staff_id",
    )
    female_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="female_side_match_cards",
        db_column="female_staff_id",
    )
    primary_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="primary_match_cards",
        db_column="primary_staff_id",
    )
    recommendation_candidate = models.ForeignKey(
        RecommendationCandidate,
        on_delete=models.PROTECT,
        related_name="match_cards",
        db_column="recommendation_candidate_id",
        null=True,
        blank=True,
    )
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default=STAGE_INITIAL_CONTACT)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default=RISK_NONE)
    risk_reason = models.ForeignKey(
        ReasonEnum,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_match_cards",
        db_column="risk_reason_id",
    )
    risk_reason_note = models.CharField(max_length=500, null=True, blank=True)
    male_feedback = models.TextField(null=True, blank=True)
    female_feedback = models.TextField(null=True, blank=True)
    male_heat = models.IntegerField(null=True, blank=True)
    female_heat = models.IntegerField(null=True, blank=True)
    staff_judgment = models.TextField(null=True, blank=True)
    last_visit_at = models.DateTimeField(null=True, blank=True)
    next_remind_at = models.DateTimeField(null=True, blank=True)
    end_reason_male = models.CharField(max_length=500, null=True, blank=True)
    end_reason_female = models.CharField(max_length=500, null=True, blank=True)
    end_reason_staff = models.CharField(max_length=500, null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "match_card"
        indexes = [
            models.Index(fields=["male_user"], name="match_card_male_user_idx"),
            models.Index(fields=["female_user"], name="match_card_female_user_idx"),
            models.Index(fields=["male_staff"], name="match_card_male_staff_idx"),
            models.Index(fields=["female_staff"], name="match_card_female_staff_idx"),
            models.Index(fields=["primary_staff"], name="match_card_primary_staff_idx"),
            models.Index(
                fields=["recommendation_candidate"], name="match_card_rec_cand_idx"
            ),
            models.Index(fields=["stage"], name="match_card_stage_idx"),
            models.Index(fields=["risk_level"], name="match_card_risk_level_idx"),
            models.Index(fields=["next_remind_at"], name="match_card_next_remind_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    stage__in=[
                        "initial_contact",
                        "stable_contact",
                        "success_pending_review",
                        "success",
                        "ended",
                    ]
                ),
                name="match_card_stage_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    risk_level__in=[
                        "none",
                        "watching",
                        "high_risk",
                    ]
                ),
                name="match_card_risk_level_valid",
            ),
        ]
