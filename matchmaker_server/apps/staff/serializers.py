from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.staff.models import Staff


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RefreshTokenRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(trim_whitespace=False)


class WechatLoginSerializer(serializers.Serializer):
    code = serializers.CharField(trim_whitespace=False)


class LoginStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ("id", "name", "role", "phone")


class StaffMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ("id", "name", "role", "phone", "wechat_id", "status")


class StaffListLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ("id", "name", "role", "status")


class StaffListFullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ("id", "name", "role", "phone", "wechat_id", "status")


class StaffWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = Staff
        fields = ("id", "name", "phone", "role", "status", "wechat_id", "password")
        read_only_fields = ("id",)

    def validate_phone(self, value):
        queryset = Staff.objects.filter(phone=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("手机号已存在")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": ["该字段为必填项。"]})
        password = attrs.get("password")
        if password:
            validate_password(password)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return Staff.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save(update_fields=[*validated_data.keys(), *(["password"] if password else []), "updated_at"])
        return instance
