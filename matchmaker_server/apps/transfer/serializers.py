from rest_framework import serializers

from apps.transfer.models import UserTransferRequest


class TransferRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    from_staff_name = serializers.CharField(source="from_staff.name", read_only=True)
    to_staff_name = serializers.CharField(source="to_staff.name", read_only=True)

    class Meta:
        model = UserTransferRequest
        fields = [
            "id",
            "user_id",
            "user_name",
            "from_staff_id",
            "from_staff_name",
            "to_staff_id",
            "to_staff_name",
            "reason",
            "status",
            "reviewer_id",
            "review_note",
            "reviewed_at",
            "created_at",
        ]


class TransferRequestCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    to_staff_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=500, allow_blank=False)


class TransferRequestRejectSerializer(serializers.Serializer):
    review_note = serializers.CharField(max_length=500, allow_blank=True, default="")
