from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.followup.models import FollowUpRecord
from apps.followup.serializers import FollowUpBaseSerializer, FollowUpWriteSerializer
from apps.followup.services import build_followup_queryset, require_followup_view_permission, valid_matched_visit_q


class FollowUpListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            FollowUpRecord.objects.select_related(
                "user",
                "match_card",
                "staff",
                "failure_reason",
                "overdue_reason",
            )
            .all()
            .order_by("-created_at", "-id")
        )
        queryset = build_followup_queryset(self.request.user, queryset)

        user_id = self.request.query_params.get("user_id")
        match_card_id = self.request.query_params.get("match_card_id")
        scene = self.request.query_params.get("scene")
        staff_id = self.request.query_params.get("staff_id")
        is_valid_visit = self.request.query_params.get("is_valid_visit")

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if match_card_id:
            queryset = queryset.filter(match_card_id=match_card_id)
        if scene:
            queryset = queryset.filter(scene=scene)
        if staff_id:
            queryset = queryset.filter(staff_id=staff_id)
        if is_valid_visit is not None:
            if is_valid_visit.lower() in {"1", "true", "yes"}:
                queryset = queryset.filter(valid_matched_visit_q())
            elif is_valid_visit.lower() in {"0", "false", "no"}:
                queryset = queryset.exclude(valid_matched_visit_q())
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FollowUpWriteSerializer
        return FollowUpBaseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_data = FollowUpBaseSerializer(instance).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class FollowUpDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = FollowUpRecord.objects.select_related(
        "user",
        "match_card",
        "staff",
        "failure_reason",
        "overdue_reason",
    ).all()

    def get_object(self):
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        require_followup_view_permission(self.request.user, obj)
        return obj

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return FollowUpWriteSerializer
        return FollowUpBaseSerializer

    def patch(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_data = FollowUpBaseSerializer(instance).data
        return Response(response_data, status=status.HTTP_200_OK)
