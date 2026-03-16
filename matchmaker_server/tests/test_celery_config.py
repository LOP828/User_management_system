"""
Celery Beat 调度配置验证。
直接断言 Django settings 中的 CELERY_BEAT_SCHEDULE，不需要真实 Redis/Worker。
"""
import pytest
from celery.schedules import crontab
from django.conf import settings


# ---------------------------------------------------------------------------
# CELERY_BEAT_SCHEDULE 存在性与结构检查
# ---------------------------------------------------------------------------


def test_celery_beat_schedule_exists():
    """CELERY_BEAT_SCHEDULE 已在 settings 中定义"""
    assert hasattr(settings, "CELERY_BEAT_SCHEDULE"), "settings 缺少 CELERY_BEAT_SCHEDULE"
    assert isinstance(settings.CELERY_BEAT_SCHEDULE, dict)
    assert len(settings.CELERY_BEAT_SCHEDULE) >= 2, "至少应有 2 个定时任务"


def test_followup_timeout_task_registered():
    """followup_timeout 定时任务已注册"""
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "reminder-scan-followup-timeout" in schedule, \
        "缺少 reminder-scan-followup-timeout 调度项"
    entry = schedule["reminder-scan-followup-timeout"]
    assert entry["task"] == "reminder.scan_followup_timeout", \
        "task 名称与 @shared_task(name=...) 不匹配"
    assert isinstance(entry["schedule"], crontab), "schedule 类型应为 crontab"


def test_first_meet_task_registered():
    """first_meet 定时任务已注册"""
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "reminder-scan-first-meet" in schedule, \
        "缺少 reminder-scan-first-meet 调度项"
    entry = schedule["reminder-scan-first-meet"]
    assert entry["task"] == "reminder.scan_first_meet", \
        "task 名称与 @shared_task(name=...) 不匹配"
    assert isinstance(entry["schedule"], crontab), "schedule 类型应为 crontab"


def test_celery_timezone_matches_django():
    """Celery 时区与 Django TIME_ZONE 一致"""
    assert settings.CELERY_TIMEZONE == settings.TIME_ZONE, \
        "CELERY_TIMEZONE 与 TIME_ZONE 不一致，会导致定时计划时区错位"


def test_celery_serializer_is_json():
    """Celery 序列化格式为 JSON（避免不安全的 pickle）"""
    assert settings.CELERY_TASK_SERIALIZER == "json"
    assert settings.CELERY_RESULT_SERIALIZER == "json"
    assert "json" in settings.CELERY_ACCEPT_CONTENT


# ---------------------------------------------------------------------------
# task 名称与 tasks.py 中 @shared_task(name=...) 的一致性检查
# ---------------------------------------------------------------------------


def test_task_names_importable():
    """tasks.py 中的 task 函数可正常导入，name 属性与 schedule 配置一致"""
    from apps.reminder.tasks import scan_first_meet, scan_followup_timeout  # noqa: PLC0415

    assert scan_followup_timeout.name == "reminder.scan_followup_timeout"
    assert scan_first_meet.name == "reminder.scan_first_meet"


def test_beat_schedule_task_names_match_task_objects():
    """CELERY_BEAT_SCHEDULE 中的 task 字符串与实际 task.name 完全吻合"""
    from apps.reminder.tasks import scan_first_meet, scan_followup_timeout  # noqa: PLC0415

    schedule = settings.CELERY_BEAT_SCHEDULE
    assert schedule["reminder-scan-followup-timeout"]["task"] == scan_followup_timeout.name
    assert schedule["reminder-scan-first-meet"]["task"] == scan_first_meet.name
