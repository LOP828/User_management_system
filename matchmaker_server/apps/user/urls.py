from django.urls import path

from apps.user.views import (
    UserDetailView,
    UserListCreateView,
    UserPauseView,
    UserResumeView,
    UserStatusChangeView,
)

urlpatterns = [
    path("", UserListCreateView.as_view(), name="user-list-create"),
    path("<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("<int:pk>/change-status/", UserStatusChangeView.as_view(), name="user-change-status"),
    path("<int:pk>/pause/", UserPauseView.as_view(), name="user-pause"),
    path("<int:pk>/resume/", UserResumeView.as_view(), name="user-resume"),
]
