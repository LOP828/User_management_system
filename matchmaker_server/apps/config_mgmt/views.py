from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsAdminRole
from apps.config_mgmt.models import PaymentLevel, ReasonEnum
from apps.config_mgmt.serializers import PaymentLevelSerializer, ReasonEnumSerializer


class ReasonEnumListCreateView(generics.ListCreateAPIView):
    queryset = ReasonEnum.objects.all().order_by("category", "sort_order", "id")
    serializer_class = ReasonEnumSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset
        category = self.request.query_params.get("category")
        is_active = self.request.query_params.get("is_active")
        if category:
            queryset = queryset.filter(category=category)
        if is_active is not None:
            is_active_value = is_active.lower()
            if is_active_value in {"true", "1"}:
                queryset = queryset.filter(is_active=True)
            elif is_active_value in {"false", "0"}:
                queryset = queryset.filter(is_active=False)
        return queryset


class ReasonEnumDetailView(generics.UpdateAPIView):
    queryset = ReasonEnum.objects.all()
    serializer_class = ReasonEnumSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ["patch"]


class PaymentLevelListCreateView(generics.ListCreateAPIView):
    queryset = PaymentLevel.objects.all().order_by("sort_order", "id")
    serializer_class = PaymentLevelSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [IsAuthenticated()]


class PaymentLevelDetailView(generics.UpdateAPIView):
    queryset = PaymentLevel.objects.all()
    serializer_class = PaymentLevelSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ["patch"]
