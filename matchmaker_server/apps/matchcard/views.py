from django.shortcuts import get_object_or_404
from django.db import models
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.matchcard.models import MatchCard
from apps.matchcard.serializers import (
    MatchCardAdvanceStageSerializer,
    MatchCardBaseSerializer,
    MatchCardCreateSerializer,
    MatchCardDetailSerializer,
    MatchCardEndSerializer,
    MatchCardRiskSerializer,
    MatchCardUpdateSerializer,
)
from apps.matchcard.services import (
    advance_match_card_stage,
    build_matchcard_queryset,
    create_match_card,
    end_match_card,
    require_matchcard_view_permission,
    set_match_card_risk,
    update_match_card,
)
from rest_framework.views import APIView


class MatchCardListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            MatchCard.objects.select_related(
                "male_user",
                "female_user",
                "male_staff",
                "female_staff",
                "primary_staff",
                "risk_reason",
            )
            .all()
            .order_by("-created_at", "-id")
        )
        queryset = build_matchcard_queryset(self.request.user, queryset)

        stage = self.request.query_params.get("stage")
        risk_level = self.request.query_params.get("risk_level")
        staff_id = self.request.query_params.get("staff_id")
        staff_role = self.request.query_params.get("staff_role")
        last_visit_before = self.request.query_params.get("last_visit_before")
        next_remind_before = self.request.query_params.get("next_remind_before")

        if stage:
            queryset = queryset.filter(stage=stage)
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        if staff_id:
            if staff_role == "male_staff":
                queryset = queryset.filter(male_staff_id=staff_id)
            elif staff_role == "female_staff":
                queryset = queryset.filter(female_staff_id=staff_id)
            elif staff_role == "primary_staff":
                queryset = queryset.filter(primary_staff_id=staff_id)
            else:
                queryset = queryset.filter(
                    models.Q(male_staff_id=staff_id)
                    | models.Q(female_staff_id=staff_id)
                    | models.Q(primary_staff_id=staff_id)
                )
        if last_visit_before:
            queryset = queryset.filter(last_visit_at__lte=last_visit_before)
        if next_remind_before:
            queryset = queryset.filter(next_remind_at__lte=next_remind_before)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MatchCardCreateSerializer
        return MatchCardBaseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = create_match_card(serializer.validated_data, request.user)
        response_data = MatchCardBaseSerializer(instance).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class MatchCardDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = MatchCard.objects.select_related(
        "male_user",
        "female_user",
        "male_staff",
        "female_staff",
        "primary_staff",
        "risk_reason",
    ).all()

    def get_object(self):
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        require_matchcard_view_permission(self.request.user, obj)
        return obj

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return MatchCardUpdateSerializer
        return MatchCardDetailSerializer

    def patch(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = update_match_card(instance, serializer.validated_data, request.user)
        response_data = MatchCardBaseSerializer(instance).data
        return Response(response_data, status=status.HTTP_200_OK)


class MatchCardAdvanceStageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        match_card = get_object_or_404(
            MatchCard.objects.select_related(
                "male_user",
                "female_user",
                "male_staff",
                "female_staff",
                "primary_staff",
                "risk_reason",
            ),
            pk=pk,
        )
        serializer = MatchCardAdvanceStageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = advance_match_card_stage(match_card, request.user, **serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class MatchCardSetRiskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        match_card = get_object_or_404(
            MatchCard.objects.select_related(
                "male_user",
                "female_user",
                "male_staff",
                "female_staff",
                "primary_staff",
                "risk_reason",
            ),
            pk=pk,
        )
        serializer = MatchCardRiskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = set_match_card_risk(
            match_card=match_card,
            actor=request.user,
            risk_level=data["risk_level"],
            risk_reason_id=data.get("risk_reason").id if data.get("risk_reason") else None,
            risk_reason_note=data.get("risk_reason_note"),
        )
        return Response(result, status=status.HTTP_200_OK)


class MatchCardEndView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        match_card = get_object_or_404(
            MatchCard.objects.select_related(
                "male_user",
                "female_user",
                "male_staff",
                "female_staff",
                "primary_staff",
                "risk_reason",
            ),
            pk=pk,
        )
        serializer = MatchCardEndSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = end_match_card(match_card, request.user, **serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)
