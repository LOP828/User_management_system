from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.services import get_admin_dashboard, get_matchmaker_dashboard
from apps.staff.models import Staff


class MatchmakerDashboardView(APIView):
    """GET /api/v1/dashboard/matchmaker/ — 红娘首页统计（仅 matchmaker 可访问）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != Staff.ROLE_MATCHMAKER:
            raise PermissionDenied("此接口仅供红娘使用")
        return Response(get_matchmaker_dashboard(request.user))


class AdminDashboardView(APIView):
    """GET /api/v1/dashboard/admin/ — 管理员首页统计（仅 admin 可访问）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != Staff.ROLE_ADMIN:
            raise PermissionDenied("此接口仅供管理员使用")
        return Response(get_admin_dashboard())
