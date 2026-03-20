from rest_framework import serializers

from apps.config_mgmt.models import ReasonEnum
from apps.followup.models import FollowUpRecord
from apps.followup.services import create_follow_up, is_valid_follow_up_record, update_follow_up
from apps.matchcard.models import MatchCard
from apps.user.models import CustomerProfile


class FollowUpBaseSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True, allow_null=True)
    match_card_id = serializers.IntegerField(source="match_card.id", read_only=True, allow_null=True)
    staff_id = serializers.IntegerField(source="staff.id", read_only=True)
    staff_name = serializers.CharField(source="staff.name", read_only=True)
    failure_reason_id = serializers.IntegerField(source="failure_reason.id", read_only=True, allow_null=True)
    overdue_reason_id = serializers.IntegerField(source="overdue_reason.id", read_only=True, allow_null=True)
    is_valid_visit = serializers.SerializerMethodField()

    class Meta:
        model = FollowUpRecord
        fields = (
            "id",
            "scene",
            "match_card_id",
            "user_id",
            "staff_id",
            "staff_name",
            "content",
            "is_still_contact",
            "risk_status",
            "next_remind_mode",
            "next_remind_at",
            "is_valid_visit",
            "failure_reason_id",
            "overdue_reason_id",
            "overdue_reason_note",
            "created_at",
        )

    def get_is_valid_visit(self, obj):
        return is_valid_follow_up_record(obj)


class MatchCardFollowUpItemSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.name", read_only=True)

    class Meta:
        model = FollowUpRecord
        fields = (
            "id",
            "staff_name",
            "content",
            "is_still_contact",
            "risk_status",
            "next_remind_mode",
            "created_at",
        )


class SuccessCaseFollowUpItemSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.name", read_only=True)
    is_valid_visit = serializers.SerializerMethodField()

    class Meta:
        model = FollowUpRecord
        fields = (
            "id",
            "staff_name",
            "content",
            "is_still_contact",
            "next_remind_mode",
            "next_remind_at",
            "is_valid_visit",
            "created_at",
        )

    def get_is_valid_visit(self, obj):
        return is_valid_follow_up_record(obj)


class FollowUpWriteSerializer(serializers.ModelSerializer):
    scene = serializers.ChoiceField(choices=FollowUpRecord.SCENE_CHOICES)
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=CustomerProfile.objects.filter(deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    match_card_id = serializers.PrimaryKeyRelatedField(
        source="match_card",
        queryset=MatchCard.objects.all(),
        required=False,
        allow_null=True,
    )
    next_remind_mode = serializers.ChoiceField(
        choices=FollowUpRecord.NEXT_REMIND_MODE_CHOICES,
        required=False,
        allow_null=True,
    )
    next_remind_at = serializers.DateTimeField(required=False, allow_null=True)
    is_still_contact = serializers.ChoiceField(
        choices=FollowUpRecord.CONTACT_STATUS_CHOICES,
        required=False,
        allow_null=True,
    )
    risk_status = serializers.ChoiceField(
        choices=FollowUpRecord.RISK_STATUS_CHOICES,
        required=False,
        allow_null=True,
    )
    failure_reason_id = serializers.IntegerField(required=False, allow_null=True)
    overdue_reason_id = serializers.IntegerField(required=False, allow_null=True)
    overdue_reason_note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)

    class Meta:
        model = FollowUpRecord
        fields = (
            "id",
            "scene",
            "match_card_id",
            "user_id",
            "content",
            "is_still_contact",
            "risk_status",
            "next_remind_mode",
            "next_remind_at",
            "failure_reason_id",
            "overdue_reason_id",
            "overdue_reason_note",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        if self.instance is not None:
            forbidden_fields = {"scene", "match_card", "user", "failure_reason_id", "overdue_reason_id", "overdue_reason_note"}
            provided = set(attrs.keys())
            illegal = provided & forbidden_fields
            if illegal:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            f"当前批次不允许修改字段：{', '.join(sorted(illegal))}。"
                        ]
                    }
                )

        scene = attrs.get("scene", getattr(self.instance, "scene", None))
        if scene not in {
            FollowUpRecord.SCENE_UNMATCHED,
            FollowUpRecord.SCENE_MATCHED,
            FollowUpRecord.SCENE_SUCCESS_FOLLOWUP,
        }:
            raise serializers.ValidationError({"scene": ["当前批次仅支持 unmatched / matched / success_followup 跟进。"]})

        match_card = attrs.get("match_card", getattr(self.instance, "match_card", None))
        user = attrs.get("user", getattr(self.instance, "user", None))
        content = attrs.get("content", getattr(self.instance, "content", None))
        is_still_contact = attrs.get("is_still_contact", getattr(self.instance, "is_still_contact", None))
        risk_status = attrs.get("risk_status", getattr(self.instance, "risk_status", None))
        next_remind_mode = attrs.get("next_remind_mode", getattr(self.instance, "next_remind_mode", None))
        next_remind_at = attrs.get("next_remind_at", getattr(self.instance, "next_remind_at", None))

        required_errors = {}
        if not content:
            required_errors["content"] = ["content 为必填项。"]
        if scene != FollowUpRecord.SCENE_UNMATCHED and match_card is None:
            required_errors["match_card_id"] = ["match_card_id 为必填项。"]
        if scene == FollowUpRecord.SCENE_MATCHED:
            if user is None:
                required_errors["user_id"] = ["user_id 为必填项。"]
            if is_still_contact is None:
                required_errors["is_still_contact"] = ["is_still_contact 为必填项。"]
            if risk_status is None:
                required_errors["risk_status"] = ["risk_status 为必填项。"]
            if next_remind_mode is None:
                required_errors["next_remind_mode"] = ["next_remind_mode 为必填项。"]
        elif scene == FollowUpRecord.SCENE_SUCCESS_FOLLOWUP:
            if is_still_contact is None:
                required_errors["is_still_contact"] = ["is_still_contact 为必填项。"]
            if next_remind_mode is None:
                required_errors["next_remind_mode"] = ["next_remind_mode 为必填项。"]
        else:
            if user is None:
                required_errors["user_id"] = ["user_id 为必填项。"]
        if required_errors:
            raise serializers.ValidationError(required_errors)

        # --- failure_reason_id: 场景限制 + 存在性 + category 校验 ---
        failure_reason_id_val = attrs.pop("failure_reason_id", None)
        if failure_reason_id_val is not None:
            if scene != FollowUpRecord.SCENE_UNMATCHED:
                raise serializers.ValidationError({
                    "failure_reason_id": ["FAILURE_REASON_NOT_ALLOWED: failure_reason_id 仅允许在 unmatched 场景使用。"]
                })
            try:
                failure_reason_obj = ReasonEnum.objects.get(id=failure_reason_id_val)
            except ReasonEnum.DoesNotExist:
                raise serializers.ValidationError({
                    "failure_reason_id": ["REASON_NOT_FOUND: 指定的失败原因不存在。"]
                })
            if failure_reason_obj.category != ReasonEnum.CATEGORY_MEET_FAILURE:
                raise serializers.ValidationError({
                    "failure_reason_id": ["INVALID_REASON_CATEGORY: failure_reason_id 必须属于 meet_failure 分类（见面失败原因）。"]
                })
            if not failure_reason_obj.is_active:
                raise serializers.ValidationError({
                    "failure_reason_id": ["REASON_NOT_FOUND: 该失败原因已停用。"]
                })
            attrs["failure_reason"] = failure_reason_obj

        # --- overdue_reason_id: 场景限制 + 存在性 + category 校验 ---
        overdue_reason_id_val = attrs.pop("overdue_reason_id", None)
        if overdue_reason_id_val is not None:
            if scene != FollowUpRecord.SCENE_UNMATCHED:
                raise serializers.ValidationError({
                    "overdue_reason_id": ["OVERDUE_REASON_NOT_ALLOWED: overdue_reason_id 仅允许在 unmatched 场景使用。"]
                })
            try:
                overdue_reason_obj = ReasonEnum.objects.get(id=overdue_reason_id_val)
            except ReasonEnum.DoesNotExist:
                raise serializers.ValidationError({
                    "overdue_reason_id": ["REASON_NOT_FOUND: 指定的超时原因不存在。"]
                })
            if overdue_reason_obj.category != ReasonEnum.CATEGORY_OVERDUE:
                raise serializers.ValidationError({
                    "overdue_reason_id": ["INVALID_REASON_CATEGORY: overdue_reason_id 必须属于 overdue 分类（超时原因）。"]
                })
            if not overdue_reason_obj.is_active:
                raise serializers.ValidationError({
                    "overdue_reason_id": ["REASON_NOT_FOUND: 该超时原因已停用。"]
                })
            attrs["overdue_reason"] = overdue_reason_obj

        # --- overdue_reason_note: 场景限制（与 overdue_reason_id 一致，仅 unmatched）---
        overdue_reason_note_val = attrs.get("overdue_reason_note")
        if overdue_reason_note_val and scene != FollowUpRecord.SCENE_UNMATCHED:
            raise serializers.ValidationError({
                "overdue_reason_note": ["OVERDUE_REASON_NOTE_NOT_ALLOWED: overdue_reason_note 仅允许在 unmatched 场景使用。"]
            })

        if scene == FollowUpRecord.SCENE_UNMATCHED:
            if match_card is not None:
                raise serializers.ValidationError({"match_card_id": ["unmatched 场景不允许填写 match_card_id。"]})
            if next_remind_at is not None and next_remind_mode is None:
                attrs["next_remind_mode"] = FollowUpRecord.REMIND_MANUAL
                next_remind_mode = FollowUpRecord.REMIND_MANUAL
            if next_remind_mode not in {None, FollowUpRecord.REMIND_MANUAL}:
                raise serializers.ValidationError({"next_remind_mode": ["unmatched 场景仅允许 manual 或不传。"]})
            return attrs

        if scene == FollowUpRecord.SCENE_SUCCESS_FOLLOWUP and user is not None:
            raise serializers.ValidationError({"user_id": ["success_followup 场景不允许填写 user_id。"]})
        if next_remind_mode == FollowUpRecord.REMIND_MANUAL and next_remind_at is None:
            raise serializers.ValidationError({"next_remind_at": ["next_remind_mode=manual 时必须填写 next_remind_at。"]})
        if next_remind_mode == FollowUpRecord.REMIND_DEFAULT and next_remind_at is not None:
            raise serializers.ValidationError({"next_remind_at": ["next_remind_mode=default 时 next_remind_at 必须为空。"]})
        return attrs

    def create(self, validated_data):
        return create_follow_up(validated_data, self.context["request"].user)

    def update(self, instance, validated_data):
        return update_follow_up(instance, validated_data, self.context["request"].user)
