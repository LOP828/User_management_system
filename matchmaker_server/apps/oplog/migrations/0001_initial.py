# Generated manually for the MVP scaffold.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OperationLog",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=50)),
                ("target_type", models.CharField(max_length=30)),
                ("target_id", models.BigIntegerField()),
                ("before_json", models.JSONField(blank=True, null=True)),
                ("after_json", models.JSONField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=500, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("operator", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="operation_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "operation_log",
            },
        ),
        migrations.AddIndex(
            model_name="operationlog",
            index=models.Index(fields=["target_type", "target_id", "created_at"], name="oplog_target_idx"),
        ),
    ]
