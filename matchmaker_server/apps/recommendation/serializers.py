from rest_framework import serializers

from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.user.services import get_pool_status_display


class RecommendationCandidateSerializer(serializers.ModelSerializer):
    candidate_user_id = serializers.IntegerField(source="candidate_user.id", read_only=True)
    candidate_user_name = serializers.CharField(source="candidate_user.name", read_only=True)

    class Meta:
        model = RecommendationCandidate
        fields = (
            "id",
            "candidate_user_id",
            "candidate_user_name",
            "is_selected",
            "is_met",
            "result",
            "created_at",
            "updated_at",
        )


class RecommendationBatchSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    staff_id = serializers.IntegerField(source="staff.id", read_only=True)
    staff_name = serializers.CharField(source="staff.name", read_only=True)
    candidates = RecommendationCandidateSerializer(many=True, read_only=True)

    class Meta:
        model = RecommendationBatch
        fields = (
            "id",
            "user_id",
            "user_name",
            "staff_id",
            "staff_name",
            "batch_no",
            "candidate_count",
            "status",
            "created_at",
            "closed_at",
            "candidates",
        )


class RecommendationBatchCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    candidate_user_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class RecommendationCandidateSearchRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    search = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    age_min = serializers.IntegerField(required=False, min_value=0)
    age_max = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        age_min = attrs.get("age_min")
        age_max = attrs.get("age_max")
        if age_min is not None and age_max is not None and age_min > age_max:
            raise serializers.ValidationError({"age_max": ["age_max 不能小于 age_min。"]})
        return attrs


class RecommendationCandidateDuplicateWarningSerializer(serializers.Serializer):
    level = serializers.CharField()
    message = serializers.CharField()
    last_batch_date = serializers.DateField()


class RecommendationCandidateSearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    gender = serializers.CharField()
    age = serializers.IntegerField()
    city = serializers.CharField()
    payment_level_name = serializers.CharField(source="payment_level.name", allow_null=True)
    pool_status_display = serializers.SerializerMethodField()
    is_profile_complete = serializers.BooleanField()
    duplicate_warning = serializers.SerializerMethodField()

    def get_pool_status_display(self, obj):
        return get_pool_status_display(obj.pool_status)

    def get_duplicate_warning(self, obj):
        warning_map = self.context.get("duplicate_warning_map", {})
        return warning_map.get(obj.id)
