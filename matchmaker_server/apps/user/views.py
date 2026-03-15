from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.user.filters import CustomerProfileFilterSet
from apps.user.models import CustomerProfile
from apps.user.serializers import (
    CustomerProfileBaseSerializer,
    CustomerProfileDetailSerializer,
    CustomerProfileListSerializer,
    CustomerProfileWriteSerializer,
    UserPauseRequestSerializer,
    UserStatusActionResponseSerializer,
    UserStatusChangeRequestSerializer,
)
from apps.user.services import (
    build_user_list_queryset,
    change_user_status,
    pause_user,
    require_user_edit_access,
    require_user_view_access,
    resume_user,
)


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    filterset_class = CustomerProfileFilterSet
    search_fields = ("name", "phone", "wechat")
    ordering_fields = ("created_at",)
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = (
            CustomerProfile.objects.filter(deleted_at__isnull=True)
            .select_related("payment_level", "owner")
            .order_by("-created_at", "-id")
        )
        queryset = build_user_list_queryset(self.request.user, queryset)
        if self.request.user.role != "admin":
            return queryset.filter(is_in_match=False)

        is_in_match = self.request.query_params.get("is_in_match")
        if is_in_match is None:
            return queryset.filter(is_in_match=False)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CustomerProfileWriteSerializer
        return CustomerProfileListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_data = CustomerProfileBaseSerializer(instance).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CustomerProfileDetailSerializer
    queryset = CustomerProfile.objects.filter(deleted_at__isnull=True).select_related("payment_level", "owner")

    def get_object(self):
        obj = super().get_object()
        require_user_view_access(self.request.user, obj)
        return obj

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return CustomerProfileWriteSerializer
        return CustomerProfileDetailSerializer

    def patch(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        require_user_edit_access(request.user, instance)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_data = CustomerProfileDetailSerializer(instance).data
        return Response(response_data, status=status.HTTP_200_OK)


class UserStatusChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = get_object_or_404(CustomerProfile, pk=pk, deleted_at__isnull=True)
        serializer = UserStatusChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = change_user_status(
            user=user,
            actor=request.user,
            **serializer.validated_data,
        )
        response_serializer = UserStatusActionResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class UserPauseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = get_object_or_404(CustomerProfile, pk=pk, deleted_at__isnull=True)
        serializer = UserPauseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = pause_user(
            user=user,
            actor=request.user,
            **serializer.validated_data,
        )
        response_serializer = UserStatusActionResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class UserResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = get_object_or_404(CustomerProfile, pk=pk, deleted_at__isnull=True)
        result = resume_user(user=user, actor=request.user)
        response_serializer = UserStatusActionResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
