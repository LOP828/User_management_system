from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from apps.common.exceptions import BusinessRuleError
from apps.staff.serializers import (
    LoginSerializer,
    RefreshTokenRequestSerializer,
    WechatLoginSerializer,
)
from apps.staff.services import build_login_response, authenticate_staff


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = authenticate_staff(**serializer.validated_data)
        return Response(build_login_response(staff), status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refresh_token"])
        except TokenError as exc:
            raise BusinessRuleError("AUTH_TOKEN_INVALID", "Token 无效", status.HTTP_401_UNAUTHORIZED) from exc

        return Response({"access_token": str(refresh.access_token)}, status=status.HTTP_200_OK)


class WechatLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = WechatLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "code": "NOT_IMPLEMENTED",
                "message": "微信登录占位接口，暂未接入真实 provider",
                "details": {},
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
