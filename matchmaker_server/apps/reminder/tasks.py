"""
Reminder Celery tasks — 定时扫描生成提醒

已实现：
  reminder.scan_followup_timeout  BR-REMIND-009 每日扫描未配对跟进超时提醒
  reminder.scan_first_meet        BR-REMIND-001 每日扫描未首见进度提醒

待实现（留待后续）：
  pause_revisit  BR-REMIND-002：暂停回访扫描，需要 user 表有 paused_at 字段确定基准时间
"""

from celery import shared_task

from apps.reminder.services import scan_first_meet_reminders, scan_followup_timeout_reminders


@shared_task(name="reminder.scan_followup_timeout")
def scan_followup_timeout():
    """
    BR-REMIND-009：每日扫描未配对用户跟进超时，生成 followup_timeout 提醒。
    建议触发时机：每日凌晨（如 00:05）。
    """
    count = scan_followup_timeout_reminders()
    return {"created": count}


@shared_task(name="reminder.scan_first_meet")
def scan_first_meet():
    """
    BR-REMIND-001：每日扫描未首见进度，按 paid_at 天数生成对应级别提醒。
    建议触发时机：每日凌晨（如 00:10）。
    """
    count = scan_first_meet_reminders()
    return {"created": count}
