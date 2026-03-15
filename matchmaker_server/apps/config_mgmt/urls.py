from django.urls import path

from apps.config_mgmt.views import (
    PaymentLevelDetailView,
    PaymentLevelListCreateView,
    ReasonEnumDetailView,
    ReasonEnumListCreateView,
)

urlpatterns = [
    path("reason-enums/", ReasonEnumListCreateView.as_view(), name="reason-enum-list-create"),
    path("reason-enums/<int:pk>/", ReasonEnumDetailView.as_view(), name="reason-enum-detail"),
    path("payment-levels/", PaymentLevelListCreateView.as_view(), name="payment-level-list-create"),
    path("payment-levels/<int:pk>/", PaymentLevelDetailView.as_view(), name="payment-level-detail"),
]
