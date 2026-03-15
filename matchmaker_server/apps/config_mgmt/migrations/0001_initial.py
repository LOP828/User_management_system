# Generated manually for the MVP scaffold.

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReasonEnum",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("category", models.CharField(choices=[("pause", "pause"), ("meet_failure", "meet_failure"), ("overdue", "overdue"), ("risk", "risk"), ("transfer", "transfer"), ("success_invalidate", "success_invalidate"), ("match_end", "match_end")], max_length=30)),
                ("label", models.CharField(max_length=100)),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "reason_enum",
            },
        ),
        migrations.AddIndex(
            model_name="reasonenum",
            index=models.Index(fields=["category", "is_active", "sort_order"], name="reason_enum_cat_idx"),
        ),
    ]
