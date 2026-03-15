from rest_framework import serializers


class ReminderListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    target_type = serializers.CharField()
    target_id = serializers.IntegerField()
    target_name = serializers.CharField()
    target_summary = serializers.CharField()
    staff_id = serializers.IntegerField()
    staff_name = serializers.CharField()
    remind_type = serializers.CharField()
    remind_type_display = serializers.CharField()
    remind_at = serializers.DateTimeField()
    status = serializers.CharField()
    is_manual = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class ReminderProcessRequestSerializer(serializers.Serializer):
    overdue_reason_id = serializers.IntegerField(required=False)
    overdue_reason_note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class ReminderProcessResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    processed_at = serializers.DateTimeField()
    created_follow_up_id = serializers.IntegerField(required=False)
