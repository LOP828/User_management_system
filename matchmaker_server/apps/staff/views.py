from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.staff.permissions import IsAdminStaff
from apps.staff.serializers import (
    StaffListFullSerializer,
    StaffListLiteSerializer,
    StaffMeSerializer,
    StaffWriteSerializer,
)


Staff = get_user_model()


class StaffMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(StaffMeSerializer(request.user).data, status=status.HTTP_200_OK)


class StaffListCreateView(generics.ListCreateAPIView):
    queryset = Staff.objects.filter(deleted_at__isnull=True).order_by("id")

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get("role")
        status_value = self.request.query_params.get("status")
        if role:
            queryset = queryset.filter(role=role)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StaffWriteSerializer
        if getattr(self.request.user, "role", None) == Staff.ROLE_ADMIN:
            return StaffListFullSerializer
        return StaffListLiteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_data = StaffMeSerializer(instance).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class StaffDetailView(generics.UpdateAPIView):
    queryset = Staff.objects.filter(deleted_at__isnull=True)
    serializer_class = StaffWriteSerializer
    permission_classes = [IsAdminStaff]

    def patch(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(StaffMeSerializer(instance).data, status=status.HTTP_200_OK)
