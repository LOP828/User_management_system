# Generated manually for recommendation persistence baseline.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("user", "0004_user_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecommendationBatch",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recommendation_batches",
                        to="user.customerprofile",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        db_column="staff_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recommendation_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("batch_no", models.CharField(max_length=50, unique=True)),
                ("candidate_count", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "open"), ("closed", "closed")],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "recommendation_batch",
            },
        ),
        migrations.CreateModel(
            name="RecommendationCandidate",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="candidates",
                        to="recommendation.recommendationbatch",
                    ),
                ),
                (
                    "candidate_user",
                    models.ForeignKey(
                        db_column="candidate_user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recommended_as_candidates",
                        to="user.customerprofile",
                    ),
                ),
                ("is_selected", models.BooleanField(default=False)),
                ("is_met", models.BooleanField(default=False)),
                (
                    "result",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("continue", "continue"),
                            ("not_continue", "not_continue"),
                            ("pending", "pending"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "recommendation_candidate",
            },
        ),
        migrations.AddIndex(
            model_name="recommendationbatch",
            index=models.Index(fields=["user", "created_at"], name="rec_batch_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="recommendationbatch",
            index=models.Index(fields=["staff"], name="rec_batch_staff_idx"),
        ),
        migrations.AddConstraint(
            model_name="recommendationbatch",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["open", "closed"]),
                name="rec_batch_status_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="recommendationcandidate",
            index=models.Index(fields=["batch"], name="rec_candidate_batch_idx"),
        ),
        migrations.AddIndex(
            model_name="recommendationcandidate",
            index=models.Index(fields=["candidate_user"], name="rec_candidate_user_idx"),
        ),
        migrations.AddConstraint(
            model_name="recommendationcandidate",
            constraint=models.CheckConstraint(
                condition=models.Q(result__isnull=True) | models.Q(result__in=["continue", "not_continue", "pending"]),
                name="rec_candidate_result_valid",
            ),
        ),
    ]
