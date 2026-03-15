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
