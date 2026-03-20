from rest_framework import serializers

from apps.oplog.models import OperationLog

ACTION_DISPLAY_MAP = {
    "user_created": "创建用户",
    "user_status_changed": "用户状态变更",
    "user_profile_updated": "用户资料更新",
    "user_paused": "用户暂停服务",
    "user_resumed": "用户恢复服务",
    "user_owner_changed": "用户负责人变更",
    "recommendation_created": "创建推荐批次",
    "candidate_selected": "选中推荐候选人",
    "close_recommendation_batch": "关闭推荐批次",
    "match_card_created": "创建配对卡",
    "match_card_stage_changed": "配对卡阶段变更",
    "match_card_risk_changed": "配对卡风险变更",
    "match_card_updated": "配对卡反馈更新",
    "match_card_ended": "配对卡结束",
    "follow_up_created": "创建跟进记录",
    "follow_up_updated": "更新跟进记录",
    "success_applied": "申请成功",
    "success_approved": "成功审批通过",
    "success_rejected": "成功审批驳回",
    "success_invalidated": "成功作废",
    "transfer_applied": "发起转移申请",
    "transfer_approved": "审批通过转移",
    "transfer_rejected": "驳回转移申请",
    "reminder_set": "设置提醒",
    "admin_force_change": "管理员强制变更",
}


class OperationLogSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source="operator.name", read_only=True)
    action_display = serializers.SerializerMethodField()

    class Meta:
        model = OperationLog
        fields = [
            "id",
            "operator_id",
            "operator_name",
            "action",
            "action_display",
            "target_type",
            "target_id",
            "before_json",
            "after_json",
            "reason",
            "created_at",
        ]

    def get_action_display(self, obj):
        return ACTION_DISPLAY_MAP.get(obj.action, obj.action)
