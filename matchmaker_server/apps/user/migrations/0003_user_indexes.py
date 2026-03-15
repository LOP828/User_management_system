# Generated manually for the MVP scaffold.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0002_user_status_history"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["owner"], name="user_owner_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["pool_status"], name="user_pool_status_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["payment_level"], name="user_payment_level_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["is_in_match"], name="user_is_in_match_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["city"], name="user_city_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["created_at"], name="user_created_at_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["paid_at"], name="user_paid_at_idx"),
        ),
        migrations.AddIndex(
            model_name="customerprofile",
            index=models.Index(fields=["last_unmatched_active_at"], name="user_last_unmatched_active_idx"),
        ),
        migrations.AddIndex(
            model_name="userstatushistory",
            index=models.Index(fields=["user", "created_at"], name="user_status_history_idx"),
        ),
    ]
