from rest_framework import serializers

from apps.config_mgmt.models import PaymentLevel, ReasonEnum


class ReasonEnumSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReasonEnum
        fields = ("id", "category", "label", "sort_order", "is_active")
        read_only_fields = ("id",)


class PaymentLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentLevel
        fields = (
            "id",
            "name",
            "sort_order",
            "is_active",
            "homepage_weight",
            "recommend_limit",
            "pause_revisit_days",
            "followup_timeout_days",
            "note",
        )
        read_only_fields = ("id",)
