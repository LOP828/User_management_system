from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.followup.models import FollowUpRecord
from apps.matchcard.models import MatchCard
from apps.reminder.models import Reminder
from apps.success.models import SuccessApplication
from apps.transfer.models import UserTransferRequest
from apps.user.models import CustomerProfile

# 进行中配对卡阶段（与 OWNER_SYNC_MATCHCARD_STAGES 保持一致）
ACTIVE_MATCHCARD_STAGES = (
    MatchCard.STAGE_INITIAL_CONTACT,
    MatchCard.STAGE_STABLE_CONTACT,
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW,
)

# 需统计的用户池状态
_USER_POOL_STATUS_KEYS = (
    (CustomerProfile.STATUS_NEW_PENDING, "new_pending"),
    (CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND, "communicated_pending_recommend"),
    (CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT, "recommended_pending_select"),
    (CustomerProfile.STATUS_SELECTED_PENDING_MEET, "selected_pending_meet"),
    (CustomerProfile.STATUS_MET_NOT_CONTINUE, "met_not_continue"),
    (CustomerProfile.STATUS_PAUSED, "paused"),
)

# 明细列表返回条目上限
_ITEMS_LIMIT = 20

# 显示映射
_POOL_STATUS_DISPLAY = {
    CustomerProfile.STATUS_NEW_PENDING: "新入库待处理",
    CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND: "已沟通待推荐",
    CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT: "已推荐待选择",
    CustomerProfile.STATUS_SELECTED_PENDING_MEET: "已选人待见面",
    CustomerProfile.STATUS_MET_NOT_CONTINUE: "已见面未继续",
    CustomerProfile.STATUS_PAUSED: "暂停服务",
}

_STAGE_DISPLAY = {
    MatchCard.STAGE_INITIAL_CONTACT: "初期接触",
    MatchCard.STAGE_STABLE_CONTACT: "稳定联系",
    MatchCard.STAGE_SUCCESS_PENDING_REVIEW: "成功待审核",
    MatchCard.STAGE_SUCCESS: "成功",
    MatchCard.STAGE_ENDED: "结束",
}

_RISK_LEVEL_DISPLAY = {
    MatchCard.RISK_NONE: "无风险",
    MatchCard.RISK_WATCHING: "关注中",
    MatchCard.RISK_HIGH_RISK: "高风险",
}


# ── 计数辅助 ──────────────────────────────────────────────────────────────


def _build_user_pool_counts(qs):
    return {key: qs.filter(pool_status=status).count() for status, key in _USER_POOL_STATUS_KEYS}


# ── BR-SORT-001 / BR-SORT-002 分数计算 ───────────────────────────────────


def _user_overdue_days(user, now):
    if not user.paid_at or not user.payment_level:
        return 0
    elapsed = (now - user.paid_at).days
    return max(elapsed - user.payment_level.followup_timeout_days, 0)


def _user_priority_score(user, now):
    score = 0
    pl = user.payment_level
    if pl:
        score += pl.homepage_weight
    overdue_days = 0
    if user.paid_at and pl:
        elapsed = (now - user.paid_at).days
        overdue_days = elapsed - pl.followup_timeout_days
        if overdue_days > 0:
            score += overdue_days * 10
    if (now - user.created_at).days <= 7:
        score += 15
    if overdue_days >= 7:
        score = max(score, 80)
    return score


def _matchcard_overdue_days(card, now):
    if not card.next_remind_at:
        return 0
    return max((now - card.next_remind_at).days, 0)


def _matchcard_priority_score(card, now):
    score = 0
    male_w = card.male_user.payment_level.homepage_weight if getattr(card.male_user, "payment_level", None) else 0
    female_w = card.female_user.payment_level.homepage_weight if getattr(card.female_user, "payment_level", None) else 0
    score += max(male_w, female_w)

    overdue_days = _matchcard_overdue_days(card, now)
    if overdue_days > 0:
        score += overdue_days * 10

    if card.risk_level == MatchCard.RISK_HIGH_RISK:
        score += 50
    elif card.risk_level == MatchCard.RISK_WATCHING:
        score += 20

    if overdue_days >= 7:
        score = max(score, 80)
    return score


# ── 明细列表构建 ──────────────────────────────────────────────────────────


def _build_unmatched_overdue(user_qs, now):
    users = user_qs.filter(paid_at__isnull=False).select_related("payment_level")
    items = []
    for user in users:
        overdue_days = _user_overdue_days(user, now)
        if overdue_days <= 0:
            continue
        items.append({
            "user_id": user.id,
            "user_name": user.name,
            "pool_status_display": _POOL_STATUS_DISPLAY.get(user.pool_status, user.pool_status),
            "payment_level_name": user.payment_level.name if user.payment_level else "",
            "overdue_days": overdue_days,
            "overdue_type": "跟进超时",
            "priority_score": _user_priority_score(user, now),
        })
    items.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"count": len(items), "items": items[:_ITEMS_LIMIT]}


def _build_matched_pending_visit(mc_qs, now):
    cards = (
        mc_qs.filter(stage__in=ACTIVE_MATCHCARD_STAGES)
        .select_related(
            "male_user__payment_level",
            "female_user__payment_level",
        )
    )
    items = []
    for card in cards:
        items.append({
            "match_card_id": card.id,
            "male_name": card.male_user.name,
            "female_name": card.female_user.name,
            "stage_display": _STAGE_DISPLAY.get(card.stage, card.stage),
            "risk_level_display": _RISK_LEVEL_DISPLAY.get(card.risk_level, card.risk_level),
            "last_visit_at": card.last_visit_at,
            "next_remind_at": card.next_remind_at,
            "overdue_days": _matchcard_overdue_days(card, now),
            "priority_score": _matchcard_priority_score(card, now),
        })
    items.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"count": len(items), "items": items[:_ITEMS_LIMIT]}


def _build_today_processed(staff_id, now):
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    qs = FollowUpRecord.objects.filter(created_at__gte=today_start)
    if staff_id:
        qs = qs.filter(staff_id=staff_id)
    return {"count": qs.count()}


def _build_recent_new(user_qs, now):
    seven_days_ago = now - timedelta(days=7)
    qs = user_qs.filter(created_at__gte=seven_days_ago)
    count = qs.count()
    recent = qs.order_by("-created_at")[:_ITEMS_LIMIT]
    items = [
        {
            "user_id": u.id,
            "user_name": u.name,
            "created_at": u.created_at,
        }
        for u in recent
    ]
    return {"count": count, "items": items}


def _build_overdue_summary(now):
    users = (
        CustomerProfile.objects.filter(
            is_in_match=False,
            deleted_at__isnull=True,
            paid_at__isnull=False,
        )
        .select_related("payment_level", "owner")
    )
    by_staff = {}
    total = 0
    for user in users:
        overdue_days = _user_overdue_days(user, now)
        if overdue_days <= 0:
            continue
        total += 1
        staff = user.owner
        if staff:
            key = staff.id
            if key not in by_staff:
                by_staff[key] = {
                    "staff_id": staff.id,
                    "staff_name": staff.name,
                    "overdue_count": 0,
                }
            by_staff[key]["overdue_count"] += 1
    by_staff_list = sorted(by_staff.values(), key=lambda x: x["overdue_count"], reverse=True)
    return {"total_overdue_users": total, "by_staff": by_staff_list}


# ── 主接口 ────────────────────────────────────────────────────────────────


def get_matchmaker_dashboard(actor):
    """
    红娘首页统计：数据范围限定在当前红娘负责 / 参与的记录。
    - user_pool: owner_id == actor.id
    - match_cards: male_staff_id 或 female_staff_id == actor.id，且阶段为进行中
    - reminders: staff_id == actor.id，status == pending
    - unmatched_overdue / matched_pending_visit / today_processed / recent_new
    """
    staff_id = actor.id
    now = timezone.now()

    user_pool_qs = CustomerProfile.objects.filter(
        owner_id=staff_id,
        is_in_match=False,
        deleted_at__isnull=True,
    )
    user_pool = _build_user_pool_counts(user_pool_qs)

    mc_base = MatchCard.objects.filter(
        Q(male_staff_id=staff_id)
        | Q(female_staff_id=staff_id)
        | Q(primary_staff_id=staff_id)
    )
    active_count = mc_base.filter(stage__in=ACTIVE_MATCHCARD_STAGES).count()
    success_pending_count = mc_base.filter(stage=MatchCard.STAGE_SUCCESS_PENDING_REVIEW).count()

    reminder_pending = Reminder.objects.filter(
        staff_id=staff_id,
        status=Reminder.STATUS_PENDING,
    ).count()

    return {
        "user_pool": user_pool,
        "match_cards": {
            "active": active_count,
            "success_pending_review": success_pending_count,
        },
        "reminders": {
            "pending": reminder_pending,
        },
        "unmatched_overdue": _build_unmatched_overdue(user_pool_qs, now),
        "matched_pending_visit": _build_matched_pending_visit(mc_base, now),
        "today_processed": _build_today_processed(staff_id, now),
        "recent_new": _build_recent_new(user_pool_qs, now),
    }


def get_admin_dashboard():
    """
    管理员首页统计：全局数据，无 staff 过滤。
    额外返回待审批数量、高风险配对卡数、超时汇总。
    """
    now = timezone.now()

    all_user_qs = CustomerProfile.objects.filter(is_in_match=False, deleted_at__isnull=True)
    user_pool = _build_user_pool_counts(all_user_qs)

    active_count = MatchCard.objects.filter(stage__in=ACTIVE_MATCHCARD_STAGES).count()
    success_pending_count = MatchCard.objects.filter(stage=MatchCard.STAGE_SUCCESS_PENDING_REVIEW).count()
    success_count = MatchCard.objects.filter(stage=MatchCard.STAGE_SUCCESS).count()
    high_risk_count = MatchCard.objects.filter(
        risk_level=MatchCard.RISK_HIGH_RISK,
        stage__in=ACTIVE_MATCHCARD_STAGES,
    ).count()

    reminder_pending = Reminder.objects.filter(status=Reminder.STATUS_PENDING).count()

    transfer_pending = UserTransferRequest.objects.filter(
        status=UserTransferRequest.STATUS_PENDING
    ).count()
    success_app_pending = SuccessApplication.objects.filter(
        status=SuccessApplication.STATUS_PENDING
    ).count()

    return {
        "user_pool": user_pool,
        "match_cards": {
            "active": active_count,
            "success_pending_review": success_pending_count,
            "success": success_count,
            "high_risk": high_risk_count,
        },
        "reminders": {
            "pending": reminder_pending,
        },
        "pending_approvals": {
            "transfer_count": transfer_pending,
            "success_count": success_app_pending,
        },
        "overdue_summary": _build_overdue_summary(now),
    }
