# 让 Django 项目启动时自动初始化 Celery app，使 @shared_task 正确绑定。
from .celery import app as celery_app

__all__ = ("celery_app",)
