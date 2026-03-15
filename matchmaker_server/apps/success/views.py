from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.success.models import SuccessApplication, SuccessCase
from apps.success.serializers import (
    SuccessApplicationApproveResponseSerializer,
    SuccessApplicationBaseSerializer,
    SuccessApplicationCreateSerializer,
    SuccessApplicationRejectResponseSerializer,
    SuccessApplicationRejectSerializer,
    SuccessCaseBaseSerializer,
    SuccessCaseDetailSerializer,
    SuccessCaseInvalidateResponseSerializer,
    SuccessCaseInvalidateSerializer,
)
from apps.success.services import (
    approve_success_application,
    build_success_application_queryset,
    build_success_case_queryset,
    invalidate_success_case,
    reject_success_application,
    _require_success_case_view_permission,
)


class SuccessApplicationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = SuccessApplication.objects.select_related(
            "match_card",
            "applicant",
            "reviewer",
        ).all().order_by("-created_at", "-id")
        queryset = build_success_application_queryset(self.request.user, queryset)
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SuccessApplicationCreateSerializer
        return SuccessApplicationBaseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_data = SuccessApplicationBaseSerializer(instance).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class SuccessApplicationApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            SuccessApplication.objects.select_related(
                "match_card",
                "applicant",
                "reviewer",
                "match_card__male_user",
                "match_card__female_user",
            ),
            pk=pk,
        )
        result = approve_success_application(application, request.user)
        response_serializer = SuccessApplicationApproveResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SuccessApplicationRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            SuccessApplication.objects.select_related(
                "match_card",
                "applicant",
                "reviewer",
            ),
            pk=pk,
        )
        serializer = SuccessApplicationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = reject_success_application(application, request.user, **serializer.validated_data)
        response_serializer = SuccessApplicationRejectResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SuccessCaseListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SuccessCaseBaseSerializer

    def get_queryset(self):
        queryset = SuccessCase.objects.select_related(
            "match_card",
            "application",
            "invalidated_reason",
            "match_card__male_user",
            "match_card__female_user",
            "match_card__primary_staff",
        ).all().order_by("-approved_at", "-id")
        queryset = build_success_case_queryset(self.request.user, queryset)
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class SuccessCaseDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SuccessCaseDetailSerializer
    queryset = SuccessCase.objects.select_related(
        "match_card",
        "application",
        "invalidated_reason",
        "match_card__male_user",
        "match_card__female_user",
        "match_card__primary_staff",
    ).all()

    def get_object(self):
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        _require_success_case_view_permission(self.request.user, obj)
        return obj


class SuccessCaseInvalidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        success_case = get_object_or_404(
            SuccessCase.objects.select_related(
                "match_card",
                "invalidated_reason",
                "match_card__male_user",
                "match_card__female_user",
                "match_card__primary_staff",
            ),
            pk=pk,
        )
        serializer = SuccessCaseInvalidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = invalidate_success_case(
            success_case,
            request.user,
            reason_id=serializer.validated_data["reason_id"],
            reason_note=serializer.validated_data.get("reason_note"),
        )
        response_serializer = SuccessCaseInvalidateResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
