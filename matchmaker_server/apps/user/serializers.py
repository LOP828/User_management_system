from django.db.models import Q
from django.utils import timezone

from rest_framework import serializers

from apps.config_mgmt.models import PaymentLevel
from apps.followup.models import FollowUpRecord
from apps.followup.serializers import FollowUpBaseSerializer
from apps.matchcard.models import MatchCard
from apps.matchcard.serializers import MatchCardBaseSerializer
from apps.recommendation.models import RecommendationCandidate
from apps.staff.models import Staff
from apps.user.models import CustomerProfile
from apps.user.services import create_customer_profile, update_customer_profile


class CustomerProfileBaseSerializer(serializers.ModelSerializer):
    payment_level_id = serializers.IntegerField(source="payment_level.id", read_only=True)
    payment_level_name = serializers.CharField(source="payment_level.name", read_only=True)
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    owner_name = serializers.CharField(source="owner.name", read_only=True)
    pool_status_display = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "name",
            "gender",
            "age",
            "phone",
            "wechat",
            "other_contact",
            "city",
            "payment_level_id",
            "payment_level_name",
            "owner_id",
            "owner_name",
            "basic_requirement",
            "pool_status",
            "pool_status_display",
            "is_profile_complete",
            "is_in_match",
            "tags",
            "paid_at",
            "created_at",
        )

    def get_pool_status_display(self, obj):
        status_map = dict(CustomerProfile.POOL_STATUS_CHOICES)
        display_map = {
            CustomerProfile.STATUS_NEW_PENDING: "新入库待处理",
            CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND: "已沟通待推荐",
            CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT: "已推荐待选择",
            CustomerProfile.STATUS_SELECTED_PENDING_MEET: "已选人待见面",
            CustomerProfile.STATUS_MET_NOT_CONTINUE: "已见面未继续",
            CustomerProfile.STATUS_PAUSED: "暂停服务",
        }
        return display_map.get(obj.pool_status, status_map.get(obj.pool_status, obj.pool_status))

    def get_tags(self, obj):
        return obj.tags or []


class CustomerProfileListSerializer(CustomerProfileBaseSerializer):
    priority_score = serializers.SerializerMethodField()

    class Meta(CustomerProfileBaseSerializer.Meta):
        fields = CustomerProfileBaseSerializer.Meta.fields + ("priority_score",)

    def get_priority_score(self, obj):
        """BR-SORT-001 / BR-SORT-002：未配对池综合排序分。

        优先使用 DB annotation（annotate_priority_score），回退到 Python 计算。
        """
        annotated = getattr(obj, "priority_score", None)
        if annotated is not None:
            return annotated

        now = timezone.now()
        score = 0
        payment_level = getattr(obj, "payment_level", None)
        if payment_level:
            score += payment_level.homepage_weight

        overdue_days = 0
        if obj.paid_at and payment_level:
            elapsed = (now - obj.paid_at).days
            overdue_days = elapsed - payment_level.followup_timeout_days
            if overdue_days > 0:
                score += overdue_days * 10

        if (now - obj.created_at).days <= 7:
            score += 15

        if overdue_days >= 7:
            score = max(score, 80)

        return score


class CustomerProfileDetailSerializer(CustomerProfileBaseSerializer):
    last_action_at = serializers.DateTimeField(read_only=True)
    last_unmatched_active_at = serializers.DateTimeField(read_only=True)
    profile_detail = serializers.SerializerMethodField()
    emotional_history = serializers.SerializerMethodField()
    recent_follow_ups = serializers.SerializerMethodField()
    active_match_card = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    class Meta(CustomerProfileBaseSerializer.Meta):
        fields = CustomerProfileBaseSerializer.Meta.fields + (
            "last_action_at",
            "last_unmatched_active_at",
            "profile_detail",
            "emotional_history",
            "recent_follow_ups",
            "active_match_card",
            "stats",
        )

    def get_profile_detail(self, obj):
        return obj.profile_detail or {}

    def get_emotional_history(self, obj):
        return obj.emotional_history or []

    def get_recent_follow_ups(self, obj):
        qs = (
            FollowUpRecord.objects.filter(user=obj, scene=FollowUpRecord.SCENE_UNMATCHED)
            .select_related("staff", "match_card", "failure_reason", "overdue_reason")
            .order_by("-created_at")[:5]
        )
        return FollowUpBaseSerializer(qs, many=True).data

    def get_active_match_card(self, obj):
        card = (
            MatchCard.objects.filter(
                Q(male_user=obj) | Q(female_user=obj),
            )
            .exclude(stage=MatchCard.STAGE_ENDED)
            .select_related(
                "male_user", "female_user",
                "male_staff", "female_staff", "primary_staff",
                "recommendation_candidate__candidate_user",
                "risk_reason",
            )
            .order_by("-created_at")
            .first()
        )
        if card is None:
            return None
        return MatchCardBaseSerializer(card).data

    def get_stats(self, obj):
        candidates = RecommendationCandidate.objects.filter(batch__user=obj)
        total_recommendations = candidates.count()
        total_meetings = candidates.filter(is_met=True).count()
        total_match_cards = MatchCard.objects.filter(
            Q(male_user=obj) | Q(female_user=obj),
        ).count()
        return {
            "total_recommendations": total_recommendations,
            "total_meetings": total_meetings,
            "total_match_cards": total_match_cards,
        }


class CustomerProfileWriteSerializer(serializers.ModelSerializer):
    payment_level_id = serializers.PrimaryKeyRelatedField(
        source="payment_level",
        queryset=PaymentLevel.objects.filter(is_active=True),
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner",
        queryset=Staff.objects.filter(
            role=Staff.ROLE_MATCHMAKER,
            status=Staff.STATUS_ACTIVE,
            deleted_at__isnull=True,
        ),
    )
    pool_status = serializers.CharField(required=False, write_only=True)
    is_profile_complete = serializers.BooleanField(required=False, write_only=True)
    is_in_match = serializers.BooleanField(required=False, write_only=True)
    created_at = serializers.DateTimeField(required=False, write_only=True)
    force = serializers.BooleanField(required=False, write_only=True)
    force_reason = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "name",
            "gender",
            "age",
            "phone",
            "wechat",
            "other_contact",
            "city",
            "payment_level_id",
            "owner_id",
            "basic_requirement",
            "profile_detail",
            "emotional_history",
            "tags",
            "paid_at",
            "pool_status",
            "is_profile_complete",
            "is_in_match",
            "created_at",
            "force",
            "force_reason",
        )
        read_only_fields = ("id", "emotional_history", "tags")

    def validate_age(self, value):
        if value < 18 or value > 100:
            raise serializers.ValidationError("年龄必须在 18-100 之间。")
        return value

    def create(self, validated_data):
        validated_data.pop("pool_status", None)
        validated_data.pop("is_profile_complete", None)
        validated_data.pop("is_in_match", None)
        validated_data.pop("created_at", None)
        validated_data.pop("force", None)
        validated_data.pop("force_reason", None)
        return create_customer_profile(validated_data, self.context["request"].user)

    def update(self, instance, validated_data):
        validated_data.pop("pool_status", None)
        validated_data.pop("is_profile_complete", None)
        validated_data.pop("is_in_match", None)
        validated_data.pop("created_at", None)
        force = validated_data.pop("force", False)
        force_reason = validated_data.pop("force_reason", None)
        return update_customer_profile(
            instance, validated_data, self.context["request"].user,
            force=force, force_reason=force_reason,
        )


class UserStatusChangeRequestSerializer(serializers.Serializer):
    to_status = serializers.CharField(max_length=30)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    force = serializers.BooleanField(required=False, default=False)
    force_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class UserPauseRequestSerializer(serializers.Serializer):
    reason_id = serializers.IntegerField(required=False, allow_null=True)
    reason_note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class UserStatusActionResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    pool_status = serializers.CharField()
    pool_status_display = serializers.CharField()
    message = serializers.CharField()
    force_applied = serializers.BooleanField(required=False)
    pre_pause_status = serializers.CharField(required=False, allow_null=True)
