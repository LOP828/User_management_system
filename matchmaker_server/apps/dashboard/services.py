from django.db.models import Q

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
    (CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND, "communicated_pending_recommend"),
    (CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT, "recommended_pending_select"),
    (CustomerProfile.STATUS_SELECTED_PENDING_MEET, "selected_pending_meet"),
    (CustomerProfile.STATUS_MET_NOT_CONTINUE, "met_not_continue"),
)


def _build_user_pool_counts(qs):
    return {key: qs.filter(pool_status=status).count() for status, key in _USER_POOL_STATUS_KEYS}


def get_matchmaker_dashboard(actor):
    """
    红娘首页统计：数据范围限定在当前红娘负责 / 参与的记录。
    - user_pool: owner_id == actor.id
    - match_cards: male_staff_id 或 female_staff_id == actor.id，且阶段为进行中
    - reminders: staff_id == actor.id，status == pending
    """
    staff_id = actor.id

    user_pool = _build_user_pool_counts(CustomerProfile.objects.filter(owner_id=staff_id))

    mc_base = MatchCard.objects.filter(
        Q(male_staff_id=staff_id) | Q(female_staff_id=staff_id)
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
    }


def get_admin_dashboard():
    """
    管理员首页统计：全局数据，无 staff 过滤。
    额外返回待审批数量和高风险配对卡数。
    """
    user_pool = _build_user_pool_counts(CustomerProfile.objects.all())

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
    }
