from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import DefaultPageNumberPagination
from apps.reminder.serializers import ReminderListItemSerializer
from apps.reminder.services import build_reminder_list


class ReminderListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        reminders = build_reminder_list(request.user, request.query_params)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reminders, request, view=self)
        serializer = ReminderListItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
