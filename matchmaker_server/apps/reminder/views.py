from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import DefaultPageNumberPagination
from apps.config_mgmt.models import ReasonEnum
from apps.reminder.models import Reminder
from apps.reminder.serializers import (
    ReminderListItemSerializer,
    ReminderProcessRequestSerializer,
    ReminderProcessResponseSerializer,
)
from apps.reminder.services import build_reminder_list, process_reminder


class ReminderListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        reminders = build_reminder_list(request.user, request.query_params)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reminders, request, view=self)
        serializer = ReminderListItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ReminderProcessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reminder = get_object_or_404(Reminder.objects.select_related("staff"), pk=pk)
        serializer = ReminderProcessRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        overdue_reason = None
        overdue_reason_id = serializer.validated_data.get("overdue_reason_id")
        if overdue_reason_id is not None:
            overdue_reason = ReasonEnum.objects.filter(id=overdue_reason_id).first()

        result = process_reminder(
            reminder,
            request.user,
            overdue_reason=overdue_reason,
            overdue_reason_note=serializer.validated_data.get("overdue_reason_note"),
        )
        response_serializer = ReminderProcessResponseSerializer(result)
        return Response(response_serializer.data)
