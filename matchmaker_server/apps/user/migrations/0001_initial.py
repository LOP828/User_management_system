# Generated manually for the MVP scaffold.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("config_mgmt", "0002_payment_level"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerProfile",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=50)),
                ("gender", models.CharField(choices=[("male", "male"), ("female", "female")], max_length=10)),
                ("age", models.PositiveIntegerField()),
                ("phone", models.CharField(blank=True, max_length=20, null=True)),
                ("wechat", models.CharField(blank=True, max_length=100, null=True)),
                ("other_contact", models.CharField(blank=True, max_length=200, null=True)),
                ("city", models.CharField(max_length=50)),
                ("basic_requirement", models.TextField()),
                ("pool_status", models.CharField(choices=[("new_pending", "new_pending"), ("communicated_pending_recommend", "communicated_pending_recommend"), ("recommended_pending_select", "recommended_pending_select"), ("selected_pending_meet", "selected_pending_meet"), ("met_not_continue", "met_not_continue"), ("paused", "paused")], default="new_pending", max_length=30)),
                ("pre_pause_status", models.CharField(blank=True, max_length=30, null=True)),
                ("is_profile_complete", models.BooleanField(default=False)),
                ("is_in_match", models.BooleanField(default=False)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("last_action_at", models.DateTimeField(blank=True, null=True)),
                ("last_unmatched_active_at", models.DateTimeField(blank=True, null=True)),
                ("profile_detail", models.JSONField(blank=True, null=True)),
                ("emotional_history", models.JSONField(blank=True, null=True)),
                ("tags", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="owned_users", to=settings.AUTH_USER_MODEL)),
                ("payment_level", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="users", to="config_mgmt.paymentlevel")),
            ],
            options={
                "db_table": "user",
            },
        ),
    ]
