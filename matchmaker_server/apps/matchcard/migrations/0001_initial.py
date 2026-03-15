# Generated manually for S03_match_card_core.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("config_mgmt", "0003_seed_reason_enum"),
        ("user", "0004_user_constraints"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchCard",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("stage", models.CharField(choices=[("initial_contact", "initial_contact"), ("stable_contact", "stable_contact"), ("success_pending_review", "success_pending_review"), ("success", "success"), ("ended", "ended")], default="initial_contact", max_length=30)),
                ("risk_level", models.CharField(choices=[("none", "none"), ("watching", "watching"), ("high_risk", "high_risk")], default="none", max_length=20)),
                ("risk_reason_note", models.CharField(blank=True, max_length=500, null=True)),
                ("male_feedback", models.TextField(blank=True, null=True)),
                ("female_feedback", models.TextField(blank=True, null=True)),
                ("male_heat", models.IntegerField(blank=True, null=True)),
                ("female_heat", models.IntegerField(blank=True, null=True)),
                ("staff_judgment", models.TextField(blank=True, null=True)),
                ("last_visit_at", models.DateTimeField(blank=True, null=True)),
                ("next_remind_at", models.DateTimeField(blank=True, null=True)),
                ("end_reason_male", models.CharField(blank=True, max_length=500, null=True)),
                ("end_reason_female", models.CharField(blank=True, max_length=500, null=True)),
                ("end_reason_staff", models.CharField(blank=True, max_length=500, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("female_staff", models.ForeignKey(db_column="female_staff_id", on_delete=django.db.models.deletion.PROTECT, related_name="female_side_match_cards", to=settings.AUTH_USER_MODEL)),
                ("female_user", models.ForeignKey(db_column="female_user_id", on_delete=django.db.models.deletion.PROTECT, related_name="female_match_cards", to="user.customerprofile")),
                ("male_staff", models.ForeignKey(db_column="male_staff_id", on_delete=django.db.models.deletion.PROTECT, related_name="male_side_match_cards", to=settings.AUTH_USER_MODEL)),
                ("male_user", models.ForeignKey(db_column="male_user_id", on_delete=django.db.models.deletion.PROTECT, related_name="male_match_cards", to="user.customerprofile")),
                ("primary_staff", models.ForeignKey(db_column="primary_staff_id", on_delete=django.db.models.deletion.PROTECT, related_name="primary_match_cards", to=settings.AUTH_USER_MODEL)),
                ("risk_reason", models.ForeignKey(blank=True, db_column="risk_reason_id", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="risk_match_cards", to="config_mgmt.reasonenum")),
            ],
            options={
                "db_table": "match_card",
            },
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["male_user"], name="match_card_male_user_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["female_user"], name="match_card_female_user_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["male_staff"], name="match_card_male_staff_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["female_staff"], name="match_card_female_staff_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["primary_staff"], name="match_card_primary_staff_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["stage"], name="match_card_stage_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["risk_level"], name="match_card_risk_level_idx"),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(fields=["next_remind_at"], name="match_card_next_remind_idx"),
        ),
        migrations.AddConstraint(
            model_name="matchcard",
            constraint=models.CheckConstraint(
                condition=models.Q(("stage__in", ["initial_contact", "stable_contact", "success_pending_review", "success", "ended"])),
                name="match_card_stage_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="matchcard",
            constraint=models.CheckConstraint(
                condition=models.Q(("risk_level__in", ["none", "watching", "high_risk"])),
                name="match_card_risk_level_valid",
            ),
        ),
    ]
