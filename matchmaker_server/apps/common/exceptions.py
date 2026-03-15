from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken


class BusinessRuleError(Exception):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _error_response(code: str, message: str, status_code: int, details=None):
    return Response(
        {
            "code": code,
            "message": message,
            "details": details or {},
        },
        status=status_code,
    )


def _contains_expired(detail) -> bool:
    if isinstance(detail, dict):
        return any(_contains_expired(value) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return any(_contains_expired(item) for item in detail)
    return "expired" in str(detail).lower()


def custom_exception_handler(exc, context):
    if isinstance(exc, BusinessRuleError):
        return _error_response(exc.code, exc.message, exc.status_code, exc.details)

    if isinstance(exc, ValidationError):
        return _error_response("VALIDATION_ERROR", "参数校验失败", status.HTTP_400_BAD_REQUEST, exc.detail)

    if isinstance(exc, (InvalidToken, AuthenticationFailed, NotAuthenticated)):
        code = "AUTH_TOKEN_EXPIRED" if _contains_expired(getattr(exc, "detail", {})) else "AUTH_TOKEN_INVALID"
        return _error_response(code, str(getattr(exc, "detail", exc)), status.HTTP_401_UNAUTHORIZED)

    if isinstance(exc, PermissionDenied):
        return _error_response("PERMISSION_DENIED", "无权限", status.HTTP_403_FORBIDDEN)

    if isinstance(exc, Http404):
        return _error_response("NOT_FOUND", "资源不存在", status.HTTP_404_NOT_FOUND)

    response = exception_handler(exc, context)
    if response is None:
        return response

    if response.status_code == status.HTTP_404_NOT_FOUND:
        return _error_response("NOT_FOUND", "资源不存在", response.status_code)

    if response.status_code == status.HTTP_403_FORBIDDEN:
        return _error_response("PERMISSION_DENIED", "无权限", response.status_code)

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "AUTH_TOKEN_EXPIRED" if _contains_expired(getattr(exc, "detail", {})) else "AUTH_TOKEN_INVALID"
        return _error_response(code, str(getattr(exc, "detail", exc)), response.status_code)

    if response.status_code == status.HTTP_400_BAD_REQUEST:
        return _error_response("VALIDATION_ERROR", "参数校验失败", response.status_code, response.data)

    return response
