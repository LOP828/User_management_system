from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import DefaultPageNumberPagination
from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.recommendation.serializers import (
    RecommendationBatchCreateSerializer,
    RecommendationBatchSerializer,
    RecommendationCandidateSearchRequestSerializer,
    RecommendationCandidateSearchResultSerializer,
    RecommendationCandidateSerializer,
)
from apps.recommendation.services import (
    build_candidate_duplicate_warning_map,
    build_candidate_search_queryset,
    build_recommendation_batch_queryset,
    close_recommendation_batch,
    create_recommendation_batch,
    get_candidate_search_target_user,
    select_candidate,
)


class RecommendationBatchListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get("user_id")

        qs = (
            RecommendationBatch.objects.select_related("user", "staff")
            .prefetch_related("candidates__candidate_user")
            .order_by("-created_at", "-id")
        )
        qs = build_recommendation_batch_queryset(request.user, qs)
        if user_id:
            qs = qs.filter(user_id=user_id)

        return Response(RecommendationBatchSerializer(qs, many=True).data)

    def post(self, request):
        serializer = RecommendationBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch, duplicate_ids = create_recommendation_batch(
            actor=request.user,
            user_id=serializer.validated_data["user_id"],
            candidate_user_ids=serializer.validated_data["candidate_user_ids"],
        )

        batch = (
            RecommendationBatch.objects.select_related("user", "staff")
            .prefetch_related("candidates__candidate_user")
            .get(id=batch.id)
        )
        response_data = RecommendationBatchSerializer(batch).data
        if duplicate_ids:
            response_data["warnings"] = [
                {"code": "BR_REC_003_DUPLICATE", "duplicate_candidate_user_ids": duplicate_ids}
            ]
        return Response(response_data, status=status.HTTP_201_CREATED)


class CandidateSelectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, candidate_id):
        candidate = select_candidate(actor=request.user, candidate_id=candidate_id)
        candidate = RecommendationCandidate.objects.select_related("candidate_user").get(id=candidate.id)
        return Response(RecommendationCandidateSerializer(candidate).data)


class CandidateSearchView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        serializer = RecommendationCandidateSearchRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        target_user = get_candidate_search_target_user(
            actor=request.user,
            user_id=serializer.validated_data["user_id"],
        )
        queryset = build_candidate_search_queryset(
            target_user=target_user,
            search=(serializer.validated_data.get("search") or "").strip() or None,
            city=(serializer.validated_data.get("city") or "").strip() or None,
            age_min=serializer.validated_data.get("age_min"),
            age_max=serializer.validated_data.get("age_max"),
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        warning_map = build_candidate_duplicate_warning_map(
            target_user=target_user,
            candidates=page,
        )
        response_serializer = RecommendationCandidateSearchResultSerializer(
            page,
            many=True,
            context={"duplicate_warning_map": warning_map},
        )
        return paginator.get_paginated_response(response_serializer.data)


class BatchCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, batch_id):
        batch = close_recommendation_batch(actor=request.user, batch_id=batch_id)
        batch = (
            RecommendationBatch.objects.select_related("user", "staff")
            .prefetch_related("candidates__candidate_user")
            .get(id=batch.id)
        )
        return Response(RecommendationBatchSerializer(batch).data)
