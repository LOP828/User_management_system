from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.staff.models import Staff
from apps.transfer.models import UserTransferRequest
from apps.transfer.serializers import (
    TransferRequestCreateSerializer,
    TransferRequestRejectSerializer,
    TransferRequestSerializer,
)
from apps.transfer.services import (
    approve_transfer_request,
    create_transfer_request,
    reject_transfer_request,
)


class TransferRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = request.user
        qs = (
            UserTransferRequest.objects
            .select_related("user", "from_staff", "to_staff")
            .order_by("-created_at")
        )
        if actor.role == Staff.ROLE_MATCHMAKER:
            qs = qs.filter(from_staff_id=actor.id)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response(TransferRequestSerializer(qs, many=True).data)

    def post(self, request):
        serializer = TransferRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        req = create_transfer_request(
            actor=request.user,
            user_id=serializer.validated_data["user_id"],
            to_staff_id=serializer.validated_data["to_staff_id"],
            reason=serializer.validated_data["reason"],
        )

        req = UserTransferRequest.objects.select_related("user", "from_staff", "to_staff").get(id=req.id)
        return Response(TransferRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class TransferRequestApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, transfer_id):
        req, affected = approve_transfer_request(actor=request.user, transfer_id=transfer_id)
        return Response({
            "id": req.id,
            "status": req.status,
            "reviewed_at": req.reviewed_at,
            "message": "转移已生效",
            "affected_match_cards": affected,
        })


class TransferRequestRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, transfer_id):
        serializer = TransferRequestRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        req = reject_transfer_request(
            actor=request.user,
            transfer_id=transfer_id,
            review_note=serializer.validated_data["review_note"],
        )
        return Response({
            "id": req.id,
            "status": req.status,
            "review_note": req.review_note,
            "reviewed_at": req.reviewed_at,
        })
