# Generated manually for the MVP scaffold.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("config_mgmt", "0002_payment_level"),
        ("user", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserStatusHistory",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("from_status", models.CharField(blank=True, max_length=30, null=True)),
                ("to_status", models.CharField(max_length=30)),
                ("reason", models.CharField(blank=True, max_length=500, null=True)),
                ("reason_note", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="user_status_changes", to=settings.AUTH_USER_MODEL)),
                ("reason_id", models.ForeignKey(blank=True, db_column="reason_id", null=True, on_delete=models.deletion.SET_NULL, related_name="user_status_histories", to="config_mgmt.reasonenum")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="status_histories", to="user.customerprofile")),
            ],
            options={
                "db_table": "user_status_history",
            },
        ),
    ]
