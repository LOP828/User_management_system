# Generated manually to align operation_log indexes with the canonical schema.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("oplog", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="operationlog",
            index=models.Index(fields=["operator", "created_at"], name="oplog_operator_idx"),
        ),
        migrations.AddIndex(
            model_name="operationlog",
            index=models.Index(fields=["created_at"], name="oplog_created_idx"),
        ),
    ]
