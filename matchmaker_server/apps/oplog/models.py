from django.conf import settings
from django.db import models


class OperationLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operation_logs")
    action = models.CharField(max_length=50)
    target_type = models.CharField(max_length=30)
    target_id = models.BigIntegerField()
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    reason = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "operation_log"
        indexes = [
            models.Index(fields=["target_type", "target_id", "created_at"], name="oplog_target_idx"),
        ]
