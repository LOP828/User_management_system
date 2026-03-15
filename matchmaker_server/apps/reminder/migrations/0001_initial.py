# Generated manually for reminder persistence baseline.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reminder",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "target_type",
                    models.CharField(
                        choices=[("user", "user"), ("match_card", "match_card")],
                        max_length=20,
                    ),
                ),
                ("target_id", models.BigIntegerField()),
                (
                    "remind_type",
                    models.CharField(
                        choices=[
                            ("normal", "normal"),
                            ("first_meet_pending", "first_meet_pending"),
                            ("first_meet_delayed", "first_meet_delayed"),
                            ("first_meet_warning", "first_meet_warning"),
                            ("first_meet_overdue", "first_meet_overdue"),
                            ("followup_timeout", "followup_timeout"),
                            ("pause_revisit", "pause_revisit"),
                            ("matched_revisit", "matched_revisit"),
                            ("success_revisit", "success_revisit"),
                            ("urgent", "urgent"),
                            ("manual", "manual"),
                        ],
                        max_length=30,
                    ),
                ),
                ("remind_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "pending"),
                            ("sent", "sent"),
                            ("processed", "processed"),
                            ("expired", "expired"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("is_manual", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "staff",
                    models.ForeignKey(
                        db_column="staff_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reminders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "reminder",
            },
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(fields=["staff", "status", "remind_at"], name="reminder_staff_status_time_idx"),
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(fields=["target_type", "target_id"], name="reminder_target_idx"),
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(fields=["remind_at", "status"], name="reminder_time_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="reminder",
            constraint=models.CheckConstraint(
                condition=models.Q(("target_type__in", ["user", "match_card"])),
                name="reminder_target_type_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="reminder",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "remind_type__in",
                        [
                            "normal",
                            "first_meet_pending",
                            "first_meet_delayed",
                            "first_meet_warning",
                            "first_meet_overdue",
                            "followup_timeout",
                            "pause_revisit",
                            "matched_revisit",
                            "success_revisit",
                            "urgent",
                            "manual",
                        ],
                    )
                ),
                name="reminder_type_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="reminder",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["pending", "sent", "processed", "expired"])),
                name="reminder_status_valid",
            ),
        ),
    ]
