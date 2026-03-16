from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.pagination import DefaultPageNumberPagination
from apps.search.serializers import UserSearchResultSerializer
from apps.search.services import build_search_queryset


class GlobalSearchView(APIView):
    """
    GET /api/v1/search/
    全局用户搜索。权限范围在 queryset 层控制：
    - matchmaker：自己负责 + 配对卡关联用户
    - admin：全局，可额外按 owner_id 过滤
    """

    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        q = request.query_params.get("q", "").strip() or None
        pool_status = request.query_params.get("pool_status") or None
        owner_id = request.query_params.get("owner_id") or None

        qs = build_search_queryset(
            request.user,
            q=q,
            pool_status=pool_status,
            owner_id=owner_id,
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = UserSearchResultSerializer(page, many=True, context={"q": q})
        return paginator.get_paginated_response(serializer.data)
