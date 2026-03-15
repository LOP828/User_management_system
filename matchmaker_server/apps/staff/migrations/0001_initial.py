# Generated manually for the MVP scaffold.

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Staff",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("name", models.CharField(max_length=50)),
                ("phone", models.CharField(max_length=20, unique=True)),
                ("role", models.CharField(choices=[("matchmaker", "matchmaker"), ("admin", "admin")], max_length=20)),
                ("status", models.CharField(choices=[("active", "active"), ("disabled", "disabled")], default="active", max_length=20)),
                ("wechat_id", models.CharField(blank=True, max_length=100, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "staff",
            },
        ),
        migrations.AddIndex(
            model_name="staff",
            index=models.Index(fields=["role"], name="staff_role_idx"),
        ),
    ]
