# Generated manually for minimal success approval flow.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("config_mgmt", "0003_seed_reason_enum"),
        ("matchcard", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SuccessApplication",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("apply_note", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "pending"), ("approved", "approved"), ("rejected", "rejected")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("review_note", models.CharField(blank=True, max_length=500, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "applicant",
                    models.ForeignKey(
                        db_column="applicant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="success_applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "match_card",
                    models.ForeignKey(
                        db_column="match_card_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="success_applications",
                        to="matchcard.matchcard",
                    ),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        db_column="reviewer_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reviewed_success_applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "success_application",
            },
        ),
        migrations.CreateModel(
            name="SuccessCase",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "active"), ("invalidated", "invalidated")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("invalidated_reason_note", models.CharField(blank=True, max_length=500, null=True)),
                ("invalidated_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "application",
                    models.ForeignKey(
                        db_column="application_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="success_cases",
                        to="success.successapplication",
                    ),
                ),
                (
                    "invalidated_reason",
                    models.ForeignKey(
                        blank=True,
                        db_column="invalidated_reason_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invalidated_success_cases",
                        to="config_mgmt.reasonenum",
                    ),
                ),
                (
                    "match_card",
                    models.ForeignKey(
                        db_column="match_card_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="success_cases",
                        to="matchcard.matchcard",
                    ),
                ),
            ],
            options={
                "db_table": "success_case",
            },
        ),
        migrations.AddIndex(
            model_name="successapplication",
            index=models.Index(fields=["match_card"], name="success_app_match_card_idx"),
        ),
        migrations.AddIndex(
            model_name="successapplication",
            index=models.Index(fields=["status"], name="success_app_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="successapplication",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["pending", "approved", "rejected"])),
                name="success_app_status_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="successcase",
            index=models.Index(fields=["status"], name="success_case_status_idx"),
        ),
        migrations.AddIndex(
            model_name="successcase",
            index=models.Index(fields=["approved_at"], name="success_case_approved_at_idx"),
        ),
        migrations.AddConstraint(
            model_name="successcase",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["active", "invalidated"])),
                name="success_case_status_valid",
            ),
        ),
    ]
