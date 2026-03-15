# Generated manually for S04_followup_core.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("config_mgmt", "0003_seed_reason_enum"),
        ("matchcard", "0001_initial"),
        ("user", "0004_user_constraints"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FollowUpRecord",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "scene",
                    models.CharField(
                        choices=[
                            ("unmatched", "unmatched"),
                            ("matched", "matched"),
                            ("success_followup", "success_followup"),
                        ],
                        max_length=20,
                    ),
                ),
                ("content", models.TextField()),
                (
                    "next_remind_mode",
                    models.CharField(
                        blank=True,
                        choices=[("manual", "manual"), ("default", "default")],
                        max_length=10,
                        null=True,
                    ),
                ),
                ("next_remind_at", models.DateTimeField(blank=True, null=True)),
                (
                    "is_still_contact",
                    models.CharField(
                        blank=True,
                        choices=[("yes", "yes"), ("no", "no"), ("unknown", "unknown")],
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "risk_status",
                    models.CharField(
                        blank=True,
                        choices=[("none", "none"), ("watching", "watching"), ("high_risk", "high_risk")],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("overdue_reason_note", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "failure_reason",
                    models.ForeignKey(
                        blank=True,
                        db_column="failure_reason_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="failure_follow_ups",
                        to="config_mgmt.reasonenum",
                    ),
                ),
                (
                    "match_card",
                    models.ForeignKey(
                        blank=True,
                        db_column="match_card_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="follow_ups",
                        to="matchcard.matchcard",
                    ),
                ),
                (
                    "overdue_reason",
                    models.ForeignKey(
                        blank=True,
                        db_column="overdue_reason_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="overdue_follow_ups",
                        to="config_mgmt.reasonenum",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        db_column="staff_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="follow_ups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        db_column="user_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="follow_ups",
                        to="user.customerprofile",
                    ),
                ),
            ],
            options={
                "db_table": "follow_up_record",
            },
        ),
        migrations.AddIndex(
            model_name="followuprecord",
            index=models.Index(fields=["user", "created_at"], name="follow_up_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="followuprecord",
            index=models.Index(fields=["match_card", "created_at"], name="follow_up_match_created_idx"),
        ),
        migrations.AddIndex(
            model_name="followuprecord",
            index=models.Index(fields=["staff"], name="follow_up_staff_idx"),
        ),
        migrations.AddConstraint(
            model_name="followuprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(("scene__in", ["unmatched", "matched", "success_followup"])),
                name="follow_up_scene_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="followuprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(next_remind_mode__isnull=True)
                | models.Q(next_remind_mode__in=["manual", "default"]),
                name="follow_up_next_remind_mode_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="followuprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(is_still_contact__isnull=True)
                | models.Q(is_still_contact__in=["yes", "no", "unknown"]),
                name="follow_up_contact_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="followuprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(risk_status__isnull=True)
                | models.Q(risk_status__in=["none", "watching", "high_risk"]),
                name="follow_up_risk_status_valid",
            ),
        ),
    ]
