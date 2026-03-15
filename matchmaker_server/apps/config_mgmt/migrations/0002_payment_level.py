# Generated manually for the MVP scaffold.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("config_mgmt", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentLevel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=50)),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("homepage_weight", models.IntegerField(default=0)),
                ("recommend_limit", models.IntegerField()),
                ("pause_revisit_days", models.IntegerField(default=30)),
                ("followup_timeout_days", models.IntegerField(default=7)),
                ("note", models.CharField(blank=True, max_length=500, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "payment_level",
            },
        ),
        migrations.AddIndex(
            model_name="paymentlevel",
            index=models.Index(fields=["is_active", "sort_order"], name="payment_level_idx"),
        ),
    ]
