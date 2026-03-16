from django.db.models import OuterRef, Q, Subquery

from apps.matchcard.models import MatchCard
from apps.staff.models import Staff
from apps.user.models import CustomerProfile
from apps.user.services import OWNER_SYNC_MATCHCARD_STAGES

# 进行中配对卡阶段，与 user.services 口径对齐
_ACTIVE_STAGES = tuple(OWNER_SYNC_MATCHCARD_STAGES)


def build_search_queryset(actor, *, q=None, pool_status=None, owner_id=None):
    """
    构建全局搜索 queryset。

    权限范围：
    - admin：全局，无 staff 过滤；可额外按 owner_id 筛选
    - matchmaker：自己负责的用户（owner_id==actor）+ 涉及自己任意配对卡的用户
    """
    if actor.role == Staff.ROLE_ADMIN:
        qs = CustomerProfile.objects.all()
        if owner_id:
            qs = qs.filter(owner_id=owner_id)
    else:
        # matchmaker 视角：owner 或配对卡相关用户（任意阶段、任意历史）
        mc_qs = MatchCard.objects.filter(
            Q(male_staff_id=actor.id)
            | Q(female_staff_id=actor.id)
            | Q(primary_staff_id=actor.id)
        )
        male_ids = mc_qs.values("male_user_id")
        female_ids = mc_qs.values("female_user_id")
        qs = CustomerProfile.objects.filter(
            Q(owner_id=actor.id) | Q(id__in=male_ids) | Q(id__in=female_ids)
        )

    # 关键词匹配：name / phone / wechat
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(wechat__icontains=q)
        )

    if pool_status:
        qs = qs.filter(pool_status=pool_status)

    # 注解当前进行中配对卡 ID（取最新一条）
    active_mc_subquery = (
        MatchCard.objects.filter(
            stage__in=_ACTIVE_STAGES,
        )
        .filter(Q(male_user=OuterRef("pk")) | Q(female_user=OuterRef("pk")))
        .order_by("-id")
        .values("id")[:1]
    )
    qs = qs.annotate(active_match_card_id=Subquery(active_mc_subquery))

    return qs.select_related("owner").order_by("-last_action_at", "-id")
