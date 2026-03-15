from django.urls import path

from apps.staff.auth_views import LoginView, RefreshTokenView, WechatLoginView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("wechat-login/", WechatLoginView.as_view(), name="auth-wechat-login"),
]
