from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.exceptions import BusinessRuleError


Staff = get_user_model()


def authenticate_staff(phone: str, password: str):
    try:
        staff = Staff.objects.get(phone=phone, deleted_at__isnull=True)
    except Staff.DoesNotExist as exc:
        raise BusinessRuleError("VALIDATION_ERROR", "手机号或密码错误", status.HTTP_400_BAD_REQUEST) from exc

    if not staff.is_active or not staff.check_password(password):
        raise BusinessRuleError("VALIDATION_ERROR", "手机号或密码错误", status.HTTP_400_BAD_REQUEST)

    return staff


def issue_tokens_for_staff(staff):
    refresh = RefreshToken.for_user(staff)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
    }


def build_login_response(staff):
    tokens = issue_tokens_for_staff(staff)
    return {
        **tokens,
        "staff": {
            "id": staff.id,
            "name": staff.name,
            "role": staff.role,
            "phone": staff.phone,
        },
    }
