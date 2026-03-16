from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.recommendation.serializers import (
    RecommendationBatchCreateSerializer,
    RecommendationBatchSerializer,
    RecommendationCandidateSerializer,
)
from apps.recommendation.services import (
    close_recommendation_batch,
    create_recommendation_batch,
    select_candidate,
)
from apps.staff.models import Staff


class RecommendationBatchListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = request.user
        user_id = request.query_params.get("user_id")

        qs = (
            RecommendationBatch.objects.select_related("user", "staff")
            .prefetch_related("candidates__candidate_user")
            .order_by("-created_at", "-id")
        )
        if actor.role == Staff.ROLE_MATCHMAKER:
            qs = qs.filter(staff_id=actor.id)
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
