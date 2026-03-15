from rest_framework import serializers

from apps.config_mgmt.models import ReasonEnum
from apps.followup.serializers import SuccessCaseFollowUpItemSerializer
from apps.followup.services import build_success_case_followups
from apps.matchcard.models import MatchCard
from apps.success.models import SuccessApplication, SuccessCase
from apps.success.services import create_success_application


class SuccessApplicationBaseSerializer(serializers.ModelSerializer):
    match_card_id = serializers.IntegerField(source="match_card.id", read_only=True)
    applicant_id = serializers.IntegerField(source="applicant.id", read_only=True)
    applicant_name = serializers.CharField(source="applicant.name", read_only=True)
    reviewer_id = serializers.IntegerField(source="reviewer.id", read_only=True, allow_null=True)
    reviewer_name = serializers.CharField(source="reviewer.name", read_only=True, allow_null=True)

    class Meta:
        model = SuccessApplication
        fields = (
            "id",
            "match_card_id",
            "applicant_id",
            "applicant_name",
            "apply_note",
            "status",
            "reviewer_id",
            "reviewer_name",
            "review_note",
            "reviewed_at",
            "created_at",
        )


class SuccessApplicationCreateSerializer(serializers.Serializer):
    match_card_id = serializers.PrimaryKeyRelatedField(source="match_card", queryset=MatchCard.objects.all())
    apply_note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        return create_success_application(validated_data, self.context["request"].user)


class SuccessApplicationApproveResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    reviewed_at = serializers.DateTimeField()
    success_case_id = serializers.IntegerField()
    message = serializers.CharField()


class SuccessApplicationRejectSerializer(serializers.Serializer):
    review_note = serializers.CharField(required=True, allow_blank=False, max_length=500)


class SuccessApplicationRejectResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    review_note = serializers.CharField()
    reviewed_at = serializers.DateTimeField()
    message = serializers.CharField()


class SuccessCaseBaseSerializer(serializers.ModelSerializer):
    match_card_id = serializers.IntegerField(source="match_card.id", read_only=True)
    application_id = serializers.IntegerField(source="application.id", read_only=True)
    invalidated_reason_id = serializers.IntegerField(source="invalidated_reason.id", read_only=True, allow_null=True)
    invalidated_reason_label = serializers.CharField(source="invalidated_reason.label", read_only=True, allow_null=True)

    class Meta:
        model = SuccessCase
        fields = (
            "id",
            "match_card_id",
            "application_id",
            "status",
            "approved_at",
            "invalidated_reason_id",
            "invalidated_reason_label",
            "invalidated_reason_note",
            "invalidated_at",
            "created_at",
            "updated_at",
        )


class SuccessCaseDetailSerializer(SuccessCaseBaseSerializer):
    male_user_id = serializers.IntegerField(source="match_card.male_user.id", read_only=True)
    male_user_name = serializers.CharField(source="match_card.male_user.name", read_only=True)
    female_user_id = serializers.IntegerField(source="match_card.female_user.id", read_only=True)
    female_user_name = serializers.CharField(source="match_card.female_user.name", read_only=True)
    primary_staff_id = serializers.IntegerField(source="match_card.primary_staff.id", read_only=True)
    primary_staff_name = serializers.CharField(source="match_card.primary_staff.name", read_only=True)
    match_card_stage = serializers.CharField(source="match_card.stage", read_only=True)
    follow_ups = serializers.SerializerMethodField()

    class Meta(SuccessCaseBaseSerializer.Meta):
        fields = SuccessCaseBaseSerializer.Meta.fields + (
            "male_user_id",
            "male_user_name",
            "female_user_id",
            "female_user_name",
            "primary_staff_id",
            "primary_staff_name",
            "match_card_stage",
            "follow_ups",
        )

    def get_follow_ups(self, obj):
        queryset = build_success_case_followups(obj)
        return SuccessCaseFollowUpItemSerializer(queryset, many=True).data


class SuccessCaseInvalidateSerializer(serializers.Serializer):
    reason_id = serializers.PrimaryKeyRelatedField(
        queryset=ReasonEnum.objects.filter(
            category=ReasonEnum.CATEGORY_SUCCESS_INVALIDATE,
            is_active=True,
        )
    )
    reason_note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)


class SuccessCaseInvalidateResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    invalidated_at = serializers.DateTimeField()
    message = serializers.CharField()
