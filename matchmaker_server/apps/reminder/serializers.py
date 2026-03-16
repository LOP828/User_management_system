from rest_framework import serializers

from apps.reminder.models import Reminder
from apps.reminder.services import build_reminder_display


class ReminderListItemSerializer(serializers.ModelSerializer):
    staff_id = serializers.IntegerField(source="staff.id", read_only=True)
    staff_name = serializers.CharField(source="staff.name", read_only=True)
    target_name = serializers.SerializerMethodField()
    target_summary = serializers.SerializerMethodField()
    remind_type_display = serializers.SerializerMethodField()

    class Meta:
        model = Reminder
        fields = (
            "id",
            "target_type",
            "target_id",
            "target_name",
            "target_summary",
            "staff_id",
            "staff_name",
            "remind_type",
            "remind_type_display",
            "remind_at",
            "status",
            "is_manual",
            "created_at",
        )

    def _get_display(self, obj):
        cache = self.context.setdefault("_reminder_display_cache", {})
        if obj.id not in cache:
            cache[obj.id] = build_reminder_display(obj)
        return cache[obj.id]

    def get_target_name(self, obj):
        return self._get_display(obj)["target_name"]

    def get_target_summary(self, obj):
        return self._get_display(obj)["target_summary"]

    def get_remind_type_display(self, obj):
        return self._get_display(obj)["remind_type_display"]


class ReminderProcessRequestSerializer(serializers.Serializer):
    overdue_reason_id = serializers.IntegerField(required=False)
    overdue_reason_note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class ReminderProcessResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    processed_at = serializers.DateTimeField()
    created_follow_up_id = serializers.IntegerField(required=False)


class ReminderManualCreateRequestSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Reminder.TARGET_TYPE_CHOICES)
    target_id = serializers.IntegerField()
    remind_at = serializers.DateTimeField()


class ReminderManualCreateResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    target_type = serializers.CharField()
    target_id = serializers.IntegerField()
    remind_type = serializers.CharField()
    remind_at = serializers.DateTimeField()
    status = serializers.CharField()
    is_manual = serializers.BooleanField()
    message = serializers.CharField()
