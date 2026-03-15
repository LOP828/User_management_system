from django.urls import path

from apps.success.views import (
    SuccessApplicationApproveView,
    SuccessApplicationListCreateView,
    SuccessApplicationRejectView,
)


urlpatterns = [
    path("", SuccessApplicationListCreateView.as_view(), name="success-application-list-create"),
    path("<int:pk>/approve/", SuccessApplicationApproveView.as_view(), name="success-application-approve"),
    path("<int:pk>/reject/", SuccessApplicationRejectView.as_view(), name="success-application-reject"),
]
