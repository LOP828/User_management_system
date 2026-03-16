# Generated manually for transfer persistence baseline.

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
            name="UserTransferRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfer_requests",
                        to="user.customerprofile",
                    ),
                ),
                (
                    "from_staff",
                    models.ForeignKey(
                        db_column="from_staff_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfer_requests_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "to_staff",
                    models.ForeignKey(
                        db_column="to_staff_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfer_requests_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("reason", models.CharField(max_length=500)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "pending"),
                            ("approved", "approved"),
                            ("rejected", "rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        db_column="reviewer_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transfer_requests_reviewed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("review_note", models.CharField(blank=True, max_length=500, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "user_transfer_request",
            },
        ),
        migrations.AddIndex(
            model_name="usertransferrequest",
            index=models.Index(fields=["user"], name="transfer_req_user_idx"),
        ),
        migrations.AddIndex(
            model_name="usertransferrequest",
            index=models.Index(fields=["status"], name="transfer_req_status_idx"),
        ),
        migrations.AddIndex(
            model_name="usertransferrequest",
            index=models.Index(fields=["from_staff"], name="transfer_req_from_staff_idx"),
        ),
        migrations.AddConstraint(
            model_name="usertransferrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["pending", "approved", "rejected"]),
                name="transfer_req_status_valid",
            ),
        ),
    ]
