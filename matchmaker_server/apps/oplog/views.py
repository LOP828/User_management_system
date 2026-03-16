from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.pagination import DefaultPageNumberPagination
from apps.oplog.models import OperationLog
from apps.oplog.serializers import OperationLogSerializer
from apps.staff.models import Staff


class OperationLogListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        if request.user.role != Staff.ROLE_ADMIN:
            raise PermissionDenied("仅管理员可查看操作日志")

        qs = OperationLog.objects.select_related("operator").order_by("-created_at")

        target_type = request.query_params.get("target_type")
        target_id = request.query_params.get("target_id")
        operator_id = request.query_params.get("operator_id")
        action = request.query_params.get("action")
        created_at_after = request.query_params.get("created_at_after")
        created_at_before = request.query_params.get("created_at_before")

        if target_type:
            qs = qs.filter(target_type=target_type)
        if target_id:
            qs = qs.filter(target_id=target_id)
        if operator_id:
            qs = qs.filter(operator_id=operator_id)
        if action:
            qs = qs.filter(action=action)
        if created_at_after:
            qs = qs.filter(created_at__gte=created_at_after)
        if created_at_before:
            qs = qs.filter(created_at__lte=created_at_before)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(OperationLogSerializer(page, many=True).data)
