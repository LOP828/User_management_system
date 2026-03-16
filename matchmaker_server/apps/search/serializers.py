from rest_framework import serializers

from apps.user.services import get_pool_status_display


class UserSearchResultSerializer(serializers.Serializer):
    """只读序列化器：搜索结果条目。"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    gender = serializers.CharField()
    age = serializers.IntegerField()
    pool_status = serializers.CharField()
    pool_status_display = serializers.SerializerMethodField()
    is_in_match = serializers.BooleanField()
    owner_id = serializers.IntegerField(source="owner.id")
    owner_name = serializers.CharField(source="owner.name")
    last_action_at = serializers.DateTimeField()
    active_match_card_id = serializers.IntegerField(allow_null=True)
    match_field = serializers.SerializerMethodField()

    def get_pool_status_display(self, obj):
        return get_pool_status_display(obj.pool_status)

    def get_match_field(self, obj):
        """返回与关键词匹配的字段名，无关键词时返回 null。"""
        q = self.context.get("q")
        if not q:
            return None
        q_lower = q.lower()
        if obj.name and q_lower in obj.name.lower():
            return "name"
        if obj.phone and q_lower in obj.phone.lower():
            return "phone"
        if obj.wechat and q_lower in obj.wechat.lower():
            return "wechat"
        return None
