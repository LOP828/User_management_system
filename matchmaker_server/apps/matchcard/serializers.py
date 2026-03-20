from rest_framework import serializers

from apps.config_mgmt.models import ReasonEnum
from apps.followup.serializers import MatchCardFollowUpItemSerializer
from apps.followup.services import build_match_card_followups, get_match_card_valid_visit_count
from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


class MatchCardBaseSerializer(serializers.ModelSerializer):
    male_user_id = serializers.IntegerField(source="male_user.id", read_only=True)
    male_user_name = serializers.CharField(source="male_user.name", read_only=True)
    female_user_id = serializers.IntegerField(source="female_user.id", read_only=True)
    female_user_name = serializers.CharField(source="female_user.name", read_only=True)
    male_staff_id = serializers.IntegerField(source="male_staff.id", read_only=True)
    male_staff_name = serializers.CharField(source="male_staff.name", read_only=True)
    female_staff_id = serializers.IntegerField(source="female_staff.id", read_only=True)
    female_staff_name = serializers.CharField(source="female_staff.name", read_only=True)
    primary_staff_id = serializers.IntegerField(source="primary_staff.id", read_only=True)
    primary_staff_name = serializers.CharField(source="primary_staff.name", read_only=True)
    candidate_id = serializers.IntegerField(source="recommendation_candidate.id", read_only=True, allow_null=True)
    candidate_user_id = serializers.IntegerField(
        source="recommendation_candidate.candidate_user.id", read_only=True, allow_null=True
    )
    candidate_user_name = serializers.CharField(
        source="recommendation_candidate.candidate_user.name", read_only=True, allow_null=True
    )
    stage_display = serializers.SerializerMethodField()
    risk_level_display = serializers.SerializerMethodField()
    risk_reason = serializers.SerializerMethodField()

    class Meta:
        model = MatchCard
        fields = (
            "id",
            "male_user_id",
            "male_user_name",
            "female_user_id",
            "female_user_name",
            "male_staff_id",
            "male_staff_name",
            "female_staff_id",
            "female_staff_name",
            "primary_staff_id",
            "primary_staff_name",
            "candidate_id",
            "candidate_user_id",
            "candidate_user_name",
            "stage",
            "stage_display",
            "risk_level",
            "risk_level_display",
            "risk_reason",
            "male_feedback",
            "female_feedback",
            "male_heat",
            "female_heat",
            "staff_judgment",
            "last_visit_at",
            "next_remind_at",
            "end_reason_male",
            "end_reason_female",
            "end_reason_staff",
            "ended_at",
            "created_at",
        )

    def get_stage_display(self, obj):
        return {
            MatchCard.STAGE_INITIAL_CONTACT: "初期接触",
            MatchCard.STAGE_STABLE_CONTACT: "稳定联系",
            MatchCard.STAGE_SUCCESS_PENDING_REVIEW: "成功待审核",
            MatchCard.STAGE_SUCCESS: "成功",
            MatchCard.STAGE_ENDED: "结束",
        }.get(obj.stage, obj.stage)

    def get_risk_level_display(self, obj):
        return {
            MatchCard.RISK_NONE: "无风险",
            MatchCard.RISK_WATCHING: "关注中",
            MatchCard.RISK_HIGH_RISK: "高风险",
        }.get(obj.risk_level, obj.risk_level)

    def get_risk_reason(self, obj):
        return obj.risk_reason.label if obj.risk_reason else None


class MatchCardDetailSerializer(MatchCardBaseSerializer):
    follow_ups = serializers.SerializerMethodField()
    valid_visit_count = serializers.SerializerMethodField()

    class Meta(MatchCardBaseSerializer.Meta):
        fields = MatchCardBaseSerializer.Meta.fields + (
            "follow_ups",
            "valid_visit_count",
        )

    def get_follow_ups(self, obj):
        queryset = build_match_card_followups(obj)
        return MatchCardFollowUpItemSerializer(queryset, many=True).data

    def get_valid_visit_count(self, obj):
        return get_match_card_valid_visit_count(obj)


class MatchCardCreateSerializer(serializers.Serializer):
    male_user_id = serializers.PrimaryKeyRelatedField(
        source="male_user",
        queryset=CustomerProfile.objects.filter(deleted_at__isnull=True),
    )
    female_user_id = serializers.PrimaryKeyRelatedField(
        source="female_user",
        queryset=CustomerProfile.objects.filter(deleted_at__isnull=True),
    )
    candidate_id = serializers.IntegerField(required=True)


class MatchCardUpdateSerializer(serializers.Serializer):
    male_feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    female_feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    male_heat = serializers.IntegerField(required=False, allow_null=True)
    female_heat = serializers.IntegerField(required=False, allow_null=True)
    staff_judgment = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class MatchCardAdvanceStageSerializer(serializers.Serializer):
    to_stage = serializers.CharField(max_length=30)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class MatchCardRiskSerializer(serializers.Serializer):
    risk_level = serializers.ChoiceField(choices=MatchCard.RISK_LEVEL_CHOICES)
    risk_reason_id = serializers.PrimaryKeyRelatedField(
        source="risk_reason",
        queryset=ReasonEnum.objects.filter(
            category=ReasonEnum.CATEGORY_RISK,
            is_active=True,
        ),
        required=False,
        allow_null=True,
    )
    risk_reason_note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)


class MatchCardEndSerializer(serializers.Serializer):
    end_reason_male = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    end_reason_female = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    end_reason_staff = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
