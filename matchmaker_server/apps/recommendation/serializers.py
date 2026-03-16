from rest_framework import serializers

from apps.recommendation.models import RecommendationBatch, RecommendationCandidate


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
